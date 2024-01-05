from pathlib import Path
from crawler_async import ImageCrawlerAsync, TextCrawlerAsync, main_async
from crawler import ImageCrawlerMultiThread, TextCrawlerMultiThread, main

ROOT = Path(r'E:\test')


def main_xbookcn():
    url = 'https://blog.xbookcn.com/'
    containers = [('div', {'class': 'post-body'}), ('p', {})]
    main(TextCrawlerMultiThread, url, ROOT, containers, max_workers=100, timeout=100)


if __name__ == '__main__':
    main_xbookcn()