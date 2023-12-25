from pathlib import Path
import re
from crawler import ImageCrawler


class MM5Crawler(ImageCrawler):

    def download(self, url, page, containers):
        title = page.find('title')
        pat = r"(?<=picinfo = \[')(.*)(?='];)"
        parent_tag, attrs = containers[0]
        contents = page.find_all(parent_tag, attrs=attrs)
        if contents:
            for content in contents:
                script = content.find('script')
                if script:
                    m = re.search(pat, script.text.replace('\n', ''))
                    if m:
                        srcs = m[1].split(',')
                        self.save(url, srcs, title, attrs)


if __name__ == '__main__':

    root = Path(r'D:\test')
    url = 'https://www.mm5mm5.com/'
    container = [('div', {'class': 'clearfloat'})]

    mm5crawler = MM5Crawler(url, root, attempt=5, timeout=(5, 10))
    mm5crawler.crawl(container)