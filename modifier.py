import os
from zipfile import ZipFile, ZIP_DEFLATED
import re
from bs4 import BeautifulSoup as Soup
from pathlib import Path
import random

IMAGES = ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff')


def walk(path):
    for root, dirs, files in os.walk(path):
        for file in files:
            yield Path(root, file)


class Modifier:

    def epub(self, src, dst, replacement_pairs, indent):
        with (ZipFile(src, 'r') as zin, ZipFile(dst, 'w') as zout):
            for info in zin.infolist():
                name = info.filename
                with zin.open(info, 'r') as f:
                    contents = f.read()
                    if name.endswith(('.xhtml', '.html')):
                        contents = contents.decode('utf-8')
                        contents = self.html(contents, replacement_pairs=replacement_pairs)
                    if name.endswith('nav.xhtml'):
                        contents = self.nav(contents, indent=indent)
                    zout.writestr(info, contents, compress_type=ZIP_DEFLATED)

    def html(self, txt, replacement_pairs=None):
        if replacement_pairs:
            for p, repl, regex in replacement_pairs:
                if regex:
                    txt = re.sub(p, repl, txt)
                else:
                    txt = txt.replace(p, repl)
        page = Soup(txt, 'lxml')
        if page.find('h1'):
            title = page.h1
            page.body.insert(0, title)
        tag = page.style
        if tag:
            tag.decompose()
        tag_sec = page.select_one('#section')
        if tag_sec:
            tag_sec.decompose()
        return str(page)

    def nav(self, txt, indent=False):
        txt = txt.replace(r'id="toc-li"', 'class="toc-li"')
        page = Soup(txt, 'lxml')
        tag_ol = page.nav.ol
        for content in tag_ol.contents:
            if content.ol:
                content.ol.decompose()
        if indent:
            tag_lis = page.select('ol > li')
            c = len(tag_lis) // (indent * 100) + 1
            for i in range(c):
                new_tag_li = page.new_tag('li', class_='toc-li')
                new_tag_a = page.new_tag('a')
                new_tag_a['href'] = tag_lis[i * indent * 100].a['href'] \
                    if i == 0 else tag_lis[i * indent * 100 - 1].a['href']
                new_tag_span = page.new_tag('span')
                new_tag_span.string = f'{i * indent * 100:04}-{(i + 1) * indent * 100 - 1:04}'
                new_tag_a.insert(0, new_tag_span)
                new_tag_li.insert(0, new_tag_a)
                new_tag_ol = page.new_tag('ol', class_='toc')
                new_tag_li.insert(1, new_tag_ol)
                start = i * indent * 100 - 1 if i != 0 else i * indent * 100
                for j, tag in enumerate(tag_lis[start:(i + 1) * indent * 100 - 1]):
                    new_tag_ol.insert(j, tag)
                tag_ol.insert(i, new_tag_li)
        return str(page)

    def md(self, file, replacement_pairs):
        pass


class Reader:
    def read(self, file, replacement_pairs=None):
        root = Path(file).parent
        with open(file, 'r', encoding='utf-8') as md:
            contents = md.read()
            if replacement_pairs:
                for p, repl, regex in replacement_pairs:
                    if regex:
                        contents = re.sub(p, repl, contents)
                    else:
                        contents = contents.replace(p, repl)
            contents = contents.replace('![](./', f'![]({root}/')
        return contents

    def merge(self, src, cat: [str | tuple], replacement_pairs: [list, tuple]) -> str:

        return ''.join(self.read(p, replacement_pairs=replacement_pairs)
                       for p in walk(src) if p.name.endswith(cat))


class Image2SlideReader(Reader):

    def read(self, file, replacement_pairs=None) -> str:

        transitions = ['fade', 'zoom', 'convex', 'concave', 'slide',]

        return (f'# {{background-image="{file}" background-size="contain" '
                f'background-transition="{random.choice(transitions)}" '
                f'background-transition-speed="slow"}}\n\n')


class TextReader(Reader):

    def read(self, file, replacement_pairs=None):
        contents = ''
        with open(file, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f.readlines()):
                if i == 0:
                    contents += f'# {line.strip()}\n\n'
                else:
                    contents += f'{line.strip()}\n\n'
        return contents


if __name__ == '__main__':
    pass

