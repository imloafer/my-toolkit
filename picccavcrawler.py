from pathlib import Path
from crawler import ImageCrawler, main


if __name__ == '__main__':
    root = Path(r'D:\test')
    url = 'https://pic.ccav.co'
    containers = [('div', {'class': 'pic-show'}), ('img', {'data-src': True})]
    main(ImageCrawler, url, root, containers, multiplier=3, timeout=1000)