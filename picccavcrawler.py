from pathlib import Path
from crawler_async import ImageCrawlerAsync, main


if __name__ == '__main__':
    root = Path(r'E:\test')
    url = 'https://pic.ccav.co'
    containers = [('div', {'class': 'pic-show'}), ('img', {'data-src': True})]
    main(ImageCrawlerAsync, url, root, containers, timeout=1000)