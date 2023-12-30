import pickle
from urllib.parse import urlparse, urlunparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup, element
import urllib3
import requests
from requests.adapters import HTTPAdapter
from fake_useragent import UserAgent

# suppress waring messages
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


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
            with self.file_urls.open('rb') as f:
                self.urls = pickle.load(f)
        except FileNotFoundError:
            self.urls = {url}
        try:
            with self.file_visited.open('rb') as f:
                self.explored = pickle.load(f)
        except FileNotFoundError:
            self.explored = set()

    def crawl(self, containers):

        while self.urls:
            url = self.urls.pop()
            if url in self.explored:
                continue
            with requests.session() as session:
                self.crawl_one(session, url, containers)

    def crawl_one(self, session, url, containers):
        print(f'Crawling {url}, total {len(self.urls)}, finished {len(self.explored)}')
        try:
            response = self._get(session, url)
            response.raise_for_status()
        except KeyboardInterrupt:
            self._restore_url(url)
        except Exception as e:
            print(f'url {url} happens {e}')
            # if error, restore unfinished url
            self.urls.add(url)
        else:
            if response:
                response.encoding = 'utf-8'
                # parse page
                page = BeautifulSoup(response.text, 'html.parser')

                # add visited url to explored set and serialize it.
                self.explored.add(url)
                self.after_work(url, page, containers=containers)

    def after_work(self, url, page, containers):
        # update links in current page
        self.update_links(url, page)

        # download specified contents
        self.download(url, page, containers=containers)

    def _get(self, session, url):
        session.headers = {'User-Agent': UserAgent().random,
                           "Accept-Encoding": "*",
                           "Connection": "keep-alive"
                           }
        adapter = HTTPAdapter(max_retries=self.attempt)
        session.mount(url, adapter)
        return session.get(url, verify=self.verify, timeout=self.timeout)

    def update_links(self, url, page):
        hostname = urlparse(url).netloc
        links = page.find_all('a', href=True)
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

    def _restore_url(self, url):
        self.urls.add(url)
        self.explored.discard(url)

    def store(self):
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
        with requests.Session() as session:
            for src in srcs:
                self._save_one(url, session, src, attr_child, hostname)

    def _save_one(self, url, session, src, attr_child, hostname):
        if isinstance(src, element.Tag):
            src = src[list(attr_child)[0]]
        u = urlparse(src)
        src = self._parse_url(u, hostname)
        p = Path(self.root, u.netloc, u.path.lstrip('/'))
        if not p.exists():
            try:
                response = self._get(session, src)
                response.raise_for_status()
            except KeyboardInterrupt:
                self._restore_url(url)
            except Exception as e:
                print(f'image {src} happens {e}')
                # if error, restore unfinished url
                self._restore_url(url)
            else:
                if response:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(response.content)
                    print(f'Saved image {src}')


class TextCrawler(Crawler):

    def save(self, url, paras, title, attrs_child):
        u = urlparse(url)
        illegal_characters = r'<>:"/\|?*'
        name = title.text.split('-')[0]
        for ic in illegal_characters:
            name = name.replace(ic, '')
        p = (Path(self.root, u.netloc, u.path.lstrip('/')).parent / name).with_suffix('.txt')
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            paras = '\n    '.join(para.text for para in paras)
            paras = f'# {name}\n\n    {paras}'
            p.write_text(paras, encoding='utf-8')
            print(f'Saved {name} {url}')


class CrawlerMultiThread(Crawler):

    def __init__(self, url, root, max_workers=5, attempt=3, timeout=(3, 5), verify=False):
        super().__init__(url, root, attempt=attempt, timeout=timeout, verify=verify)
        self.max_workers = max_workers

    def crawl(self, containers):
        ttl = len(self.urls)
        while ttl < self.max_workers + 1:
            urls = [url for _ in range(ttl)
                    if (url := self.urls.pop()) not in self.explored]
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                with requests.Session() as session:
                    futures = [executor.submit(self.crawl_one, session, url, containers) for url in urls]
            if (ttl := len(self.urls)) == 0:
                return
        urls = [url for _ in range(self.max_workers+1)
                if (url := self.urls.pop()) not in self.explored]
        while (lng := len(urls)) < self.max_workers and ttl >= (diff := self.max_workers - lng):
            urls += [url for _ in range(diff)
                     if (url := self.urls.pop()) not in self.explored]
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            with requests.Session() as session:
                futures = [executor.submit(self.crawl_one, session, url, containers) for url in urls]
                while self.urls:
                    for future in as_completed(futures):
                        url = self.urls.pop()
                        f = executor.submit(self.crawl_one, session, url, containers)
                        futures.remove(future)
                        futures.append(f)

    def after_work(self, url, page, containers):
        with ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(self.update_links, url, page)
            executor.submit(self.download, url, page, containers=containers)


class ImageCrawlerMultiThread(CrawlerMultiThread, ImageCrawler):

    def save(self, url, srcs, title, attr_child):
        hostname = urlparse(url).hostname
        with ThreadPoolExecutor() as executor:
            with requests.Session() as session:
                for src in srcs:
                    executor.submit(self._save_one, url, session, src, attr_child, hostname)


class TextCrawlerMultiThread(CrawlerMultiThread, TextCrawler):

    pass


def main(Krawler, url, root, containers, **kwargs):
    crawler = Krawler(url, root, **kwargs)
    try:
        crawler.crawl(containers)
    finally:
        crawler.store()


if __name__ == '__main__':
    pass
