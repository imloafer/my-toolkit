import os
import os.path
import pypandoc
from zipfile import ZipFile, ZIP_DEFLATED
import re
from bs4 import BeautifulSoup as bs
from tempfile import TemporaryDirectory
from pathlib import Path


class Converter:
    def __init__(self, source_path):
        self.source_path = source_path

    def merge(self, cat, to, dest_path, dest_name, replacement_pairs, options=None):
        """
        merge two or more files to a specified format, such as epub, pdf or any
        format which pandoc can convert.
        :param cat: file name or file types, can be a single or a tuple, transfer
                    to _read() function.
        :param to:  format to merge, any format that pandoc can convert to.
        :param dest_path: destination path that converted file will be written to.
        :param dest_name: final output file name.
        :param replacement_pairs: any text pattern(s) that will be replaced
                                  and will be replaced with, it is a three element tuple,
                                  the last one is a bool to identify to use re or replacement.
        :param options: options for pandoc.
        :return:  a path to a merged file
        """
        from_ = cat.split('.')[-1]
        out_name = Path(dest_path, dest_name)
        with TemporaryDirectory() as td:
            path = Path(td, dest_name + from_)
            with open(path, 'a', encoding='utf-8') as f:
                for root, dirs, files in os.walk(self.source_path):
                    for file in files:
                        if file.endswith(cat):
                            source = Path(root, file)
                            f.write(self._read(source, replacement_pairs))
            return self.convert(path, from_, to, out_name, options)

    def _read(self, file, replacement_pairs=None):
        """
        read from specified format.
        :param replacement_pairs: any text pattern(s) that will be replaced
                                  and will be replaced with, it is a three element tuple,
                                  the last one is a bool to identify to use re or replacement.
        :return:
        """
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

    def one_by_one(self, cat, to, replacement_pairs=None, options=None):
        """
        convert from one format to another format one by one.
        :param cat:
        :param to:
        :param replacement_pairs:
        :param options:
        :return:
        """
        from_ = cat.split('.')[-1]
        with TemporaryDirectory() as td:
            for root, dirs, files in os.walk(self.source_path):
                for file in files:
                    if file.endswith(cat):
                        root = Path(root)
                        path = source = root / file
                        if replacement_pairs:
                            path = Path(td, file)
                            with open(path, 'w+', encoding='utf-8') as f:
                                f.write(self._read(source, replacement_pairs))
                        out_name = source.parent
                        self.convert(path, from_, to, out_name, options)

    def convert(self, source, fr, to, out_path_with_out_name, options=None):
        """
        main converter which invokes pandoc to convert from one format to another
        :param source: source file with full path.
        :param fr: original file format, normally is file extension without dot.
        :param to: output format, normally is file extension without dot
        :param out_path_with_out_name: path and file name without extension.
        :param options: any options to pass to pandoc
        :return: output file with full path
        """
        out_file = Path(f'{out_path_with_out_name}.{to}')
        pypandoc.convert_file(source, to, fr, options, outputfile=out_file)
        return out_file

    def extract_epub(self, source_file):
        extract_path, _ = os.path.splitext(source_file)
        with ZipFile(source_file, 'r') as zf:
            zf.extractall(extract_path)
        return extract_path

    def modify_epub(self, source_file, dest_path, dest_name, replacement_pairs=None, indent=False):
        output_name = Path(dest_path)/f'{dest_name}.epub'
        with (ZipFile(source_file, 'r') as zin, ZipFile(output_name, 'w') as zout):
            for info in zin.infolist():
                name = info.filename
                with zin.open(info, 'r') as f:
                    contents = f.read()
                    if name.endswith(('.xhtml', '.html')):
                        contents = contents.decode('utf-8')
                        contents = self._html(contents, replacement_pairs)
                        if name.endswith('nav.xhtml'):
                            contents = self._nav(contents, indent)
                        zout.writestr(info, contents, compress_type=ZIP_DEFLATED)
                    else:
                        zout.writestr(info, contents, compress_type=ZIP_DEFLATED)

    def _html(self, txt, replacement_pairs=None):

        if replacement_pairs:
            for p, repl, regex in replacement_pairs:
                if regex:
                    txt = re.sub(p, repl, txt)
                else:
                    txt = txt.replace(p, repl)
        page = bs(txt, 'lxml')
        if page.find('h1'):
            title = page.h1
            page.body.insert(0, title)
        tag = page.style
        if tag:
            tag.decompose()
        tag_sec = page.select_one('#section')
        if tag_sec:
            tag_sec.decompose()

        # only for go2epub
        # page = self._for_go2epub_only(page)
        return str(page)

    def _for_go2epub_only(self, page):
        tables = page.find_all('table')
        if tables and len(tables) > 1:
            last_table = tables[-1]
            last_table.decompose()
        colgroups = page.find_all('colgroup')
        if colgroups:
            for col in colgroups:
                col.decompose()
        trs = page.find_all('tr')
        if trs:
            last_tr = trs[-1]
            last_tr.decompose()
            for tr in trs:
                ths = tr.find_all('th')
                if ths:
                    ths[1].decompose()
                    ths[2].decompose()
                tds = tr.find_all('td')
                if tds:
                    s = tds[0].string
                    c = s.count('0')
                    new_span = page.new_tag('span')
                    new_span.string = f'{tds[0].string}. {tds[1].string}'
                    new_a = page.new_tag('a')
                    m = s if c == 0 else s[1:]
                    new_a['href'] = f'../../leetcode/text/ch{m}.xhtml'
                    new_a.insert(0, new_span)
                    tds[0].string = ''
                    tds[0].insert(0, new_a)
                    tds[1].decompose()
                    tds[2].decompose()
        divs = page.find_all('div')
        if divs:
            last_div = divs[-1]
            last_div.decompose()
        return page

    def _nav(self, txt, indent=False):
        txt = txt.replace(r'id="toc-li"', 'class="toc-li"')
        page = bs(txt, 'lxml')
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


def merge2epub(cat,
               source_path,
               dest_path,
               dest_name,
               read_replacement_pairs=None,
               write_replacement_pairs=None,
               options=None,
               indent=False):
    if indent:
        if not isinstance(indent, int):
            print('indent should be bool (True or False) or integer between 1 - 9')
            return
        elif indent > 9 or indent < 0:
            print('indent is too big, it should be between 1 - 9')
            return

    converter = Converter(source_path)
    to = 'epub'
    if write_replacement_pairs:
        with TemporaryDirectory() as td:
            source = converter.merge(cat, to, td, dest_name, read_replacement_pairs, options)
            converter.modify_epub(source, dest_path, dest_name, write_replacement_pairs, indent)
    else:
        converter.merge(cat, to, dest_path, dest_name, read_replacement_pairs, options)


def leetcode2epub(cat, source_path, dest_path, dest_name, indent=False):

    def rep(m):
        lng = len(m[2])
        m2 = m[2] if lng > 2 else '0' + m[2] if lng == 2 else '00' + m[2]
        return f'{m[1]}(ch{m2}.xhtml)'

    def rep1(m):
        lng = len(m[2])
        m2 = m[2] if lng > 2 else '0' + m[2] if lng == 2 else '00' + m[2]
        return f'{m[1]}<a href="../../leetcode/text/ch{m2}.xhtml">{m[2]}</a>{m[3]}'

    ver = 'English Version' if cat == 'README.md' else '中文文档'
    read_replacement_pairs = [(rf'\[{ver}\].*', '', True),
                              # change to local absolute path
                              (r'https://fastly.jsdelivr.net/gh/doocs/leetcode@main', 'D:/github/leetcode', False),
                              (r'### **C++**', '### **Cplusplus**', False),   # reserve C++
                              (r'### **C#**', '### **Csharpsharp**', False),  # reserve C#
                              (r'(\[(\d{1,4})\..*?])\(/solution/.*?\)', rep, True),  # in site page link
                              # in site page link
                              (r'(本题与主站 )(\d{1,4})(.*?)(<a href=")(https://.*?)(">)\5</a>', rep1, True),
                              (r'<!-- tabs:start -->', '<ul class="tab" id="tab"></ul>', False),  # add tab tag
                              (r'(?<=```)(\w+)(?=\n)', r'\1 {.numberLines}', True), # add code line number
                              # (r'.*?\[开源社区 Doocs\].*', '', True),
                              # (r'快速搜索题号、题解、标签等，请善用.*', '', True),
                              # (r'## 版权', '', False),
                              # (r'著作权归 \[GitHub 开源社区 Doocs\].*', '', True),
                              ]
    write_replacement_pairs = [(r'plusplus', '++', False),  # restore C++ name
                               (r'sharpsharp', '#', False),  # restore C# name
                               # remove extra id numbers produced by pandoc
                               (r'(<section .*?id=".*?)\-\d+', r'\1', True),
                               # remove something between src=" and http://
                               (r'(?<=src=").*?(?=http://)', '', True),
                               ]
    options = ['--mathml',       # math formula
               '--standalone',
               '--include-after-body=after.txt',   # insert <script></script> tag before </body> to set js path
               f'--resource-path={dest_path}',
               '--epub-title-page=False',
               '--css=D:/test/styles/stylesheet1.css',  # insert customized css
               f'--metadata=title:{dest_name}',
               ]
    merge2epub(cat,
               source_path,
               dest_path,
               dest_name,
               read_replacement_pairs,
               write_replacement_pairs,
               options,
               indent)


def go2epub(cat, source_path, dest_path, dest_name, indent=False):

    read_replacement_pairs = [(r'### **C++**', '### **Cplusplus**', False),
                              (r'### **C#**', '### **Csharpsharp**', False),
                              (r'(?<=```)(\w+)(?=\n)', r'\1 {.numberLines}', True),  # add code line number
                              ]
    write_replacement_pairs = [  # (r'<!-- tabs:start -->', '<ul class="tab" id="tab"></ul>', False),  # add tab tag
                               (r'plusplus', '++', False),  # restore C++ name
                               (r'sharpsharp', '#', False),  # restore C# name
                               (r'style=".*?"', '', True),
                               (r'(<section .*?id=".*?)\-\d+', r'\1', True),
                               # remove extra id numbers produced by pandoc
                               (r'(?<=src=").*?(?=http://)', '', True),  # remove something between src=" and http://

                               ]
    options = ['--mathml',
               '--standalone',
               '--include-after-body=after.txt',
               f'--resource-path={dest_path}',
               '--epub-title-page=False',
               '--css=D:/test/styles/stylesheet1.css',
               f'--metadata=title:{dest_name}',
               ]
    merge2epub(cat,
               source_path,
               dest_path,
               dest_name,
               read_replacement_pairs,
               write_replacement_pairs,
               options,
               indent)


if __name__ == '__main__':

    cat = 'README.md'
    source_path = Path(r'D:\github\leetcode\solution')
    dest_path = Path(r'D:\test')
    dest_name = source_path.name
    leetcode2epub(cat, source_path, dest_path, dest_name, indent=True)








