import pypandoc
from tempfile import TemporaryDirectory
from pathlib import Path
from modifier import walk, Reader, Modifier, TextReader, IMAGES


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
            print('indent should be between 1 - 9')
            return
    to = 'epub'
    fr = cat.split('.')[-1]
    modifier = Modifier()
    reader = Reader()
    dst = Path(dest_path, f'{dest_name}.{to}')
    contents = reader.merge(source_path, cat, read_replacement_pairs)
    if write_replacement_pairs:
        with TemporaryDirectory() as td:
            out_file = Path(td, f'{dest_name}.{to}')
            pypandoc.convert_text(contents, to, fr, options, outputfile=out_file)
            modifier.epub(out_file, dst, write_replacement_pairs, indent=indent)
    else:
        pypandoc.convert_text(contents, to, fr, options, outputfile=dst)


def txt2epub(src, dest, name, photo_path=None, indent=False):

    out_path = Path(dest, f'{name}.epub')
    options = ['--standalone',
               '--epub-title-page=False',
               '--css=D:/pandoc/styles/stylesheet1.css',
               f'--metadata=title:{dest_name}',
               ]

    if indent:
        if not isinstance(indent, int):
            print('indent should be bool (True or False) or integer between 1 - 9')
            return
        elif indent > 9 or indent < 0:
            print('indent should be between 1 - 9')
            return

    reader = TextReader()
    contents = reader.merge(src, '.txt', replacement_pairs=None)

    if photo_path is not None:
        photos = [p for p in walk(photo_path) if p.name.endswith(IMAGES)]
        photos_copy = photos[:]
        tmp = ''
        for line in contents.splitlines(keepends=True):
            try:
                pic = photos_copy.pop()
            except IndexError:
                photos_copy = photos[:]
                pic = photos_copy.pop()
            if line.startswith('#'):
                tmp += f'{line}\n![]({pic})\n'
            else:
                tmp += line
        contents = tmp

    if indent:
        modifier = Modifier()
        with TemporaryDirectory() as td:
            _out_path = Path(td, f'{name}.epub')
            pypandoc.convert_text(contents, 'epub', 'markdown', extra_args=options, outputfile=_out_path)
            modifier.epub(_out_path, out_path, replacement_pairs=None, indent=indent)
    else:
        pypandoc.convert_text(contents, 'epub', 'markdown', extra_args=options, outputfile=out_path)


if __name__ == '__main__':

    cat = 'README.md'
    source_path = Path(r'D:\software\novel\photo\gallery')
    dest_path = Path(r'D:\test')
    # photo_path = Path(r'D:\software\novel\photo')
    dest_name = source_path.name
    # txt2epub(source_path, photo_path, dest_path, dest_name, indent=True)
    # leetcode2epub(cat, source_path, dest_path, dest_name, indent=False)








