from bs4 import BeautifulSoup
from pathlib import Path
from crawler import TextCrawler
from modifier import walk


def distill(path):
    path = Path(path)
    dummy = TextCrawler('www.sample.com', 'd:\\test')
    for p in walk(path):
        if p.name.endswith(('.html', '.xhtml')):
            with p.open('r', encoding='utf-8') as f:
                page = BeautifulSoup(f.read(), 'html.parser')
                contents = page.find('div', {'class': 'post-content'})
                title = page.find('title')
                paras = contents.find_all('p')
                if paras:
                    print('saving...', url, title.text)
                    mode = 'w'

                    # if '?page' in url:
                    #     mode = 'a'
                    # dummy.save(title, paras, path, mode)


if __name__ == '__main__':
    root = Path(r'D:\test')
    url = 'https://dwkm.xyz'
    container = [('div', {'class': 'post-content'}), ('p', {})]
    crawler = TextCrawler(url, root, timeout=1000)
    crawler.crawl(container)
