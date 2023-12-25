import pickle
from urllib.parse import urlparse, urlunparse
from bs4 import BeautifulSoup, element
from pathlib import Path
import requests
from requests.packages import urllib3
from requests.adapters import HTTPAdapter
from fake_useragent import UserAgent


class Crawler:

    def __init__(self, url, root, attempt=3, timeout=(3, 5), verify=False):

        u = urlparse(url)
        if u.scheme == '':
            u = u._replace(scheme='https')
        url = urlunparse(u)
        self.root = root
        self.attempt = attempt
        self.timeout = timeout
        self.verify = verify
        self.domain = u.netloc
        self.file_urls = Path(self.domain).with_suffix('.url.pickle')
        self.file_visited = Path(self.domain).with_suffix('.visited.pickle')

        # check if the site crawled before, if then start from last url.
        try:
            with open(self.file_urls, 'rb') as f:
                self.urls = pickle.load(f)
        except FileNotFoundError:
            self.urls = {url}
        try:
            with open(self.file_visited, 'rb') as f:
                self.explored = pickle.load(f)
        except FileNotFoundError:
            self.explored = set()

    def crawl(self, container):
        urllib3.disable_warnings()  # suppress waring messages

        while self.urls:
            url = self.urls.pop()
            if url in self.explored:
                continue
            print('url is ', url, 'total is ', len(self.urls), 'finished ', len(self.explored))
            try:
                response = self._get(url)
            except Exception as e:
                print(url)
                print(e)
                # if error, restore unfinished url
                self._restore(url)
                break
            else:
                if response:
                    response.encoding = 'utf-8'
                    # parse page
                    page = BeautifulSoup(response.text, 'html.parser')

                    # add visited url to explored set and serialize it.
                    self.explored.add(url)
                    self._serialize(self.file_visited, self.explored)

                    # update links in current page
                    self.update_links(url, page)

                    # download specified contents
                    self.download(url, page, containers=container)

    def _get(self, url):

        session = requests.Session()
        session.headers = {'User-Agent': UserAgent().random,
                           "Accept-Encoding": "*",
                           "Connection": "keep-alive"
                           }
        adapter = HTTPAdapter(max_retries=self.attempt)
        session.mount(url, adapter)
        return session.get(url, verify=self.verify, timeout=self.timeout)

    def update_links(self, url, page):
        hostname = urlparse(url).netloc
        links = page.find_all('a', href=True, id=False)
        for link in links:
            href = link['href']
            u = urlparse(href)
            if u.netloc != '' and u.netloc != hostname:
                continue
            href = self._parse_url(u, hostname)
            if href not in self.explored:
                self.urls.add(href)
        self._serialize(self.file_urls, self.urls)

    def _parse_url(self, parsed_url, hostname):

        if parsed_url.scheme == '':
            parsed_url = parsed_url._replace(scheme='https')
        if parsed_url.netloc == '':  # convert relative url to absolute url
            parsed_url = parsed_url._replace(netloc=hostname)
        return urlunparse(parsed_url)

    def _serialize(self, path, obj):
        with open(path, 'wb') as f:
            pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)

    def _restore(self, url):
        self.urls.add(url)
        self.explored.discard(url)
        self._serialize(self.file_urls, self.urls)
        self._serialize(self.file_visited, self.explored)

    def download(self, url, page, containers):
        title = page.find('title')
        parent_tag, attrs = containers[0]
        contents = page.find_all(parent_tag, attrs=attrs)
        if contents:
            child_tag, attr_child = containers[1]
            for content in contents:
                targets = content.find_all(child_tag, attrs=attr_child)
                if targets:
                    self.save(url, targets, title, attr_child)

    def save(self, url, targets, title, attr_child):
        raise NotImplemented


class ImageCrawler(Crawler):

    def save(self, url, srcs, title, attr_child):
        hostname = urlparse(url).hostname
        for src in srcs:
            if isinstance(src, element.Tag):
                src = src[list(attr_child)[0]]
            u = urlparse(src)
            src = self._parse_url(u, hostname)
            p = Path(self.root, u.netloc, u.path.lstrip('/'))
            if not Path(p).exists():
                try:
                    response = self._get(src)
                except Exception as e:
                    print(url)
                    print(e)
                    # if error, restore unfinished url
                    self._restore(url)
                else:
                    if response:
                        p.parent.mkdir(parents=True, exist_ok=True)
                        with p.open('wb') as f:
                            f.write(response.content)
                        print(src, 'finished downloading')


class TextCrawler(Crawler):

    def save(self, url, paras, title, attrs_child):
        u = urlparse(url)
        path = Path(self.root, u.netloc, u.path.lstrip('/')).parent
        illegal_characters = r'<>:"/\|?*'
        name = title.text.split('-')[0]
        for ic in illegal_characters:
            name = name.replace(ic, '')
        out_path = Path(path, name).with_suffix('.txt')
        if not Path(out_path).exists():
            path.mkdir(parents=True, exist_ok=True)
            paras = '\n    '.join(p.text for p in paras)
            with open(out_path, 'w', encoding='utf-8') as out:
                out.write(f'# {name}\n\n    ')
                out.write(paras)
            print('saved...', url, title.text)


if __name__ == '__main__':
    root = Path(r'D:\test')
    url = 'https://pic.ccav.co'
    containers = [('div', {'class': 'pic-show'}), ('img', {'data-src': True})]
    crawler = ImageCrawler(url, root, timeout=1000)
    crawler.crawl(containers)
