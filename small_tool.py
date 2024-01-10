import asyncio
from pathlib import Path
import shutil
import re
import xml.etree.ElementTree as et

from modifier import walk


async def rename(path, pattern, repl=''):
    """
    batch clear unwanted characters in a filename in specified path.
    :param path: directory to files to be renamed.
    :param pattern: regular expressions or normal string.
    :param repl: string will be replaced to, default is ''.
    :return: None
    """

    coco = [asyncio.to_thread(p.rename(p.with_name(re.sub(pattern, repl, p.name))))
            for p in walk(path)]
    await asyncio.gather(*coco)


async def srt2vtt_all(path):
    """batch convert srt subtitle to vtt subtitle"""

    coco = [asyncio.to_thread(srt2vtt, p) for p in walk(path) if p.suffix == '.srt']
    await asyncio.gather(*coco)


def srt2vtt(srt: Path):
    """convert single srt file to vtt file"""

    vtt: Path = srt.with_suffix('.vtt')
    shutil.copy(srt, vtt)
    content = vtt.read_text(encoding='utf-8')
    content = re.sub(r'(\d)(,)(\d)', lambda m: m[1] + '.' + m[3], content)
    content = f'WEBVTT\n\n{content}'
    vtt.write_text(content, encoding='utf-8')


def epub_ncx2html(file, classname='html'):
    """
    to convert epub toc file to a html tag file in text format.
    converted text and output a text file in the same path as original .ncx file.
    :param file: epub toc file with suffix .ncx, such as A.ncx
    :param classname: tag class name which want to add to ul tag
    :return: None.
    """
    ns = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
    file = Path(file)
    tree = et.parse(file)
    root = tree.getroot()
    nav_map = root.find('./ncx:navMap', ns)
    out_name = root.find('./ncx:docTitle//ncx:text', ns).text
    if ":" in out_name:
        out_name = out_name.split(':')[0]
    output = file.with_name(out_name).with_suffix('.txt')

    details = et.Element("details", attrib={'class': "tier1"})
    et.SubElement(details, "summary").text = out_name
    ul = et.SubElement(details, "ul", attrib={'class': classname})

    def traverse(origin_root, new_root, new_element):
        children = origin_root.findall('./ncx:navPoint', ns)
        for i in range(len(children)):
            if children[i].find('./ncx:navPoint', ns):
                _new_root = et.SubElement(new_root, "details")
                et.SubElement(_new_root, "summary",
                              attrib={'id': children[i].find('./ncx:content', ns).attrib['src']}).text \
                    = children[i].find('.//ncx:text', ns).text
                if i == 0:
                    new_root.remove(new_element)
                _new_element = et.SubElement(_new_root, "ul", attrib={'class': classname})
                traverse(children[i], _new_root, _new_element)
            else:
                if i > 0 and children[i - 1].find('./ncx:navPoint', ns):
                    new_element = et.SubElement(new_root, 'ul', attrib={'class': classname})

                new_sub_element = et.SubElement(new_element, "li", attrib={'class': 'playlist ' + classname,
                                                'id': children[i].find('./ncx:content', ns).attrib['src']})
                new_sub_element.text = children[i].find('.//ncx:text', ns).text
        return

    traverse(nav_map, details, ul)
    tree = et.ElementTree(details)
    et.indent(details, space='    ', level=0)
    tree.write(output, encoding='utf-8')


if __name__ == '__main__':
    pass
