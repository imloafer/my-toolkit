from pathlib import Path
from bs4 import BeautifulSoup
from make_epub import merge2epub
from modifier import Modifier


class GoModifier(Modifier):

    def html(self, txt, replacement_pair=None):
        contents = super().html(txt, replacement_pair)
        page = BeautifulSoup(contents, 'html.parser')
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
        return str(page)


def go2epub(cat, source_path, dest_path, dest_name, indent):

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
               mod=GoModifier,
               read_replacement_pairs=read_replacement_pairs,
               write_replacement_pairs=write_replacement_pairs,
               options=options,
               indent=indent)


if __name__ == '__main__':
    cat = 'README.md'
    source_path = Path(r'D:\software\novel\photo\gallery')
    dest_path = Path(r'D:\test')
    dest_name = source_path.name
    go2epub(cat, source_path, dest_path, dest_name, indent=False)