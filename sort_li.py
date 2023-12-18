import os
from pathlib import Path


def sort_li(path):
    for root, dirs, files in os.walk(path):
        for file in files:
            full_path = Path(root, file)
            with open(full_path, 'r', encoding='utf-8') as f:
                contents = [line for line in f.read().split('\n') if line.strip()]
            lis = contents[2:-2]
            lis.sort(key=lambda x: int(x.split('<span>')[1].split('</span>')[0]))
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(contents[:2] + lis + contents[-2:]))


if __name__ == '__main__':

    path = Path(r'D:\test\video')
    sort_li(path)