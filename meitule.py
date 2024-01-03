from pathlib import Path
from crawler import ImageCrawler, ImageCrawlerMultiThread, main


if __name__ == '__main__':
    root = Path(r'E:\test')
    url = 'https://www.meitule.net'
    containers = [('div', {'class': 'content'}), ('img', {'src': True})]
    main(ImageCrawlerMultiThread, url, root, containers, max_workers=20, timeout=(5, 10))