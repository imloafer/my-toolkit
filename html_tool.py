import os
import re
from bs4 import BeautifulSoup as BS


class HtmlTool:
    """
    series tools for html page modification or assistant.
    """

    def __init__(self, file_path):
        self.file_path = file_path

    def __get_files(self):

        for root, dirs, files in os.walk(self.file_path, topdown=False):
            for file in files:
                yield root, file, os.path.splitext(file)[-1]

    def clear_dir(self, pattern, repl=''):

        """
        clear unwanted characters in certain directory name
        :param pattern: string or regular expression.
        :param repl: string will be replaced to, default is ''.
        :return: None
        """

        for root, dirs, files in os.walk(self.file_path):
            for _dir in dirs:
                _dir = os.path.join(root, _dir)
                new_dir = re.sub(pattern, repl, _dir)
                os.rename(_dir, new_dir)

    def make_list(self):
        """scan a fold
            1, output .mp3 and mp4 files' name to a html list template:
               <li class="playing audio or video" id="filename with full path">
               filename without suffix</li>;
            2, write to a output.txt file.
        """

        illegal_chars = (re.compile(r"#"), re.compile(r"\+"))  # define illegal characters in file name;
        txt_file_path = self.file_path + "\\" + "output.txt"  # define output file name and path
        li = ""

        for root, file, suffix in self.__get_files():
            old_file_path = os.path.join(root, file)
            for char in illegal_chars:
                file = re.sub(char, "", file)
            new_file_path = os.path.join(root, file)
            os.rename(old_file_path, new_file_path)
            filename = os.path.splitext(file)[0]
            id_path = os.path.join(root, filename)
            if suffix in [".mp4", ".mp3", ".html", ".xhtml"]:
                with open(txt_file_path, "w+", encoding="utf-8") as f:
                    if suffix == ".mp4":
                        li += f"<li class=\"playlist video\" id=\"{id_path!s}\">{filename!s}</li>\n"
                    elif suffix == ".mp3":
                        li += f"<input class=\"btn\" type=\"button\" id=\"{id_path!s}\"/>\n"
                    elif suffix == ".html" or suffix == ".xhtml":
                        li += f"<li class=\"playlist html\" id=\"{id_path!s}{suffix!s}\">{' '.join(filename.split('_'))!s}</li>\n"
                    f.write(li)

    def merge_two_web_pages(self, page_file1, page_file2):

        """
        merge two web pages to one
        :param page_file1: first web page file with path
        :param page_file2: second web page file with path
        :return: merged two pages contents
        """

        with open(page_file1, 'r', encoding='utf-8') as f:
            page1 = BS(f.read(), "lxml")
            body1 = page1.body
        with open(page_file2, 'r', encoding='utf-8') as f:
            page = BS(f.read(), 'lxml')
            body = page.find('body')
            body_contents = body.findChildren(recursive=False)
        for item in body_contents:
            body1.append(item)

        return page1

    def make_paragraph(self, tag, classname):

        chinese_chars = \
            re.compile(r'([\u4e00-\u9fa5\u3002\uff1b\uff0c\uff1a\u201c\u201d\uff08\uff09\u3001\uff1f\u300a\u300b].*?$)')
        html_chars = re.compile(r"<.*?>$")

        def add_html_element(txt):
            matches = re.finditer(chinese_chars, txt)
            for m in matches:
                txt = txt.replace(m.group(1), f"<span lang=\"zh\">{m.group(1)}</span>")
            return txt.replace("\n", "").strip()

        for root, file, suffix in self.__get_files():
            temps = []
            file_path = os.path.join(root, file)
            print(file)
            if suffix == ".txt":
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    find = re.search(html_chars, lines[0])
                    if find:
                        continue
                    else:
                        title = f"<h3>{add_html_element(lines[0])}</h3>"
                        temps.append(title)
                        for line in lines[1:]:
                            line = f"<{tag!s} class=\"{classname!s}\">{add_html_element(line)!s}</{tag!s}>"
                            temps.append(line)

                with open(file_path, "w+", encoding="utf-8") as f:
                    for temp in temps:
                        temp = temp + "\n"
                        f.write(temp)


if __name__ == "__main__":

    path = r'D:\下载'
    # p = r' ?\(z-lib\.org\)| ?\(b-ok\.cc\)| ? by it-ebooks| ?- ?libgen\.li| ?\(Z-Library\)'
    # ht = HtmlTool(path)
    # ht.make_list()

    # ht.rename_dir(pat)
    # epub_ncx2html(path)
