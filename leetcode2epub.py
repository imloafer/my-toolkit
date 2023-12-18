from pathlib import Path
from make_epub import merge2epub


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
                              (r'(?<=```)(\w+)(?=\n)', r'\1 {.numberLines}', True),  # add code line number
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
               # insert <script></script> tag before </body> to set js path
               '--include-after-body=D:/pandoc/after.txt',
               '--epub-title-page=False',
               '--css=D:/pandoc/styles/stylesheet1.css',  # insert customized css
               f'--metadata=title:{dest_name}',
               ]
    merge2epub(cat,
               source_path,
               dest_path,
               dest_name,
               read_replacement_pairs,
               write_replacement_pairs,
               options,
               indent=indent)


if __name__ == '__main__':
    cat = 'README.md'
    source_path = Path(r'D:\test\lcci')
    dest_path = Path(r'D:\test')
    dest_name = source_path.name
    leetcode2epub(cat, source_path, dest_path, dest_name, indent=False)