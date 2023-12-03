import os
import re
import shutil
import xml.etree.ElementTree as ET
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

    def rename(self, pattern, repl=''):
        """
        clear unwanted characters in a filename
        :param pattern: regular expressions or normal string.
        :param repl: string will be replaced to, default is ''.
        :return: None
        """

        for root, file, suffix in self.__get_files():
            file_path = os.path.join(root, file)
            file = re.sub(pattern, repl, file)
            new_file_path = os.path.join(root, file)
            os.rename(file_path, new_file_path)

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

    def srt2vtt(self):
        """convert srt subtitle to vtt subtitle"""

        for root, file, suffix in self.__get_files():
            if suffix == ".srt":
                name = os.path.splitext(file)[0]
                vtt_file = name + ".vtt"
                srt_path = os.path.join(root, file)
                vtt_path = os.path.join(root, vtt_file)
                shutil.copy(srt_path, vtt_path)

                with open(vtt_path, 'r', encoding="UTF-8") as f:
                    a = f.read()

                a = re.sub(r'(\d)(,)(\d)', lambda m: m[1]+'.'+m[3], a)

                with open(vtt_path, "w+", encoding='utf-8') as f:
                    f.seek(0)
                    f.write("WEBVTT\n\n")
                    f.write(a)

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


def epub_ncx2html(file, classname='html'):
    """
    to convert epub toc file to a html tag file in text format.
    :param file: epub toc file with suffix .ncx, such as A.ncx
    :param classname: tag class name which want to add to ul tag
    :return: None.
    converted text and output a text file in the same path as original .ncx file.
    """
    ns = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
    tree = ET.parse(file)
    root = tree.getroot()
    nav_map = root.find('./ncx:navMap', ns)
    file_name = root.find('./ncx:docTitle//ncx:text', ns).text
    if ":" in file_name:
        file_name = file_name.split(':')[0]
    output = os.path.join(os.path.split(file)[0], file_name + ".txt")

    details = ET.Element("details", attrib={'class': "tier1"})
    ET.SubElement(details, "summary").text = file_name
    ul = ET.SubElement(details, "ul", attrib={'class': classname})

    def traverse(origin_root, new_root, new_element):
        children = origin_root.findall('./ncx:navPoint', ns)
        for i in range(len(children)):
            if children[i].find('./ncx:navPoint', ns):
                _new_root = ET.SubElement(new_root, "details")
                ET.SubElement(_new_root, "summary",
                              attrib={'id': children[i].find('./ncx:content', ns).attrib['src']}).text \
                    = children[i].find('.//ncx:text', ns).text
                if i == 0:
                    new_root.remove(new_element)
                _new_element = ET.SubElement(_new_root, "ul", attrib={'class': classname})
                traverse(children[i], _new_root, _new_element)
            else:
                if i > 0 and children[i - 1].find('./ncx:navPoint', ns):
                    new_element = ET.SubElement(new_root, 'ul', attrib={'class': classname})

                new_sub_element = ET.SubElement(new_element, "li", attrib={'class': 'playlist ' + classname,
                                    'id': children[i].find('./ncx:content', ns).attrib['src']})
                new_sub_element.text = children[i].find('.//ncx:text', ns).text
        return

    traverse(nav_map, details, ul)
    tree = ET.ElementTree(details)
    ET.indent(details, space='    ', level=0)
    tree.write(output, encoding='utf-8')


if __name__ == "__main__":

    path = r'D:\test\The Markdown Guide (Matt Cone)\OEBPS\toc.ncx'
    # p = r' ?\(z-lib\.org\)| ?\(b-ok\.cc\)| ? by it-ebooks| ?- ?libgen\.li| ?\(Z-Library\)'
    p = r'\.xhtml'
    repl = '.html'
    # ht = HtmlTool(path)
    # ht.rename(p, repl)
    # ht.srt2vtt()
    # ht.make_list()

    # ht.rename_dir(pat)
    epub_ncx2html(path)
