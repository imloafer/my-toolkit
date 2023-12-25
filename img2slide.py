from pathlib import Path
from tempfile import TemporaryDirectory
import pypandoc
from modifier import Image2SlideReader
from constants import IMAGES


def img2slide(src_path, dest_path, dest_name, revealjs_path='D:/pandoc/reveal.js'):

    options = ['--standalone',
               '--embed-resource',
               f'--metadata=title:{dest_name}',
               '-V', f'revealjs-url={revealjs_path}',
               ]
    out_path = Path(dest_path, dest_name).with_suffix('.html')
    reader = Image2SlideReader()
    contents = reader.merge(src_path, IMAGES, replacement_pairs=None)

    with TemporaryDirectory() as td:
        temp_path = Path(td, dest_name).with_suffix('.html')
        pypandoc.convert_text(contents, 'revealjs', 'markdown', extra_args=options, outputfile=temp_path)
        with open(temp_path, 'r', encoding='utf-8') as inf, open(out_path, 'w', encoding='utf-8') as outf:
            contents = ''.join(line for line in inf.readlines() if not line.startswith('<h1'))
            outf.write(contents)


if __name__ == '__main__':

    source_path = Path(r'D:\software\novel\photo\gallery\1')
    dest_path = Path(r'D:\test')
    dest_name = source_path.name
    revealjs_path = 'D:/pandoc/reveal.js'
    img2slide(source_path, dest_path, dest_name)
