from pathlib import Path
from crawler import ImageCrawlerMultiThread, main


if __name__ == '__main__':
    root = Path(r'D:\test')
    url = 'https://www.meitule.net'
    containers = [('div', {'class': 'content'}), ('img', {'src': True})]
    main(ImageCrawlerMultiThread, url, root, containers, max_workers=10, timeout=(5, 10))