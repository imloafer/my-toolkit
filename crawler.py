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

        # check if the site crawled before, if then start from arbitrary url.
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
                self._crawl_one(session, url, containers)

    def _crawl_one(self, session, url, containers):
        print(f'Crawling {url}, total {len(self.urls)}, finished {len(self.explored)}')
        page = self._get(session, url, url, self._parse_html)
        if page:
            self._distill(url, page, containers=containers)

    def _parse_html(self, resp):
        return BeautifulSoup(resp.text, 'html.parser')

    def _distill(self, url, page, containers):
        # update links in current page
        self._update_links(url, page)

        # download specified contents
        self._download(url, page, containers=containers)

    def _get(self, session, url, ori_url, f, *args):
        session.headers = {'User-Agent': UserAgent().random,
                           "Accept-Encoding": "*",
                           "Connection": "keep-alive"
                            }
        adapter = HTTPAdapter(max_retries=self.attempt)
        session.mount(url, adapter)
        try:
            r = session.get(url, verify=self.verify, timeout=self.timeout)
            r.raise_for_status()
        except KeyboardInterrupt:
            self._restore_url(ori_url)
        except Exception as e:
            print(f'{url} happens {e}')
            # if error, restore unfinished url
            self._restore_url(ori_url)
        else:
            r.encoding = 'utf-8'
            self.explored.add(url)
            return f(r, *args)

    def _update_links(self, url, page):
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

    def _parse_url(self, parsed_url, hostname):

        if parsed_url.scheme == '':
            parsed_url = parsed_url._replace(scheme='https')
        if parsed_url.netloc == '':  # convert relative url to absolute url
            parsed_url = parsed_url._replace(netloc=hostname)
        return urlunparse(parsed_url)

    def _restore_url(self, url):
        self.urls.add(url)
        self.explored.discard(url)

    def store(self):
        with self.file_urls.open('wb') as f_urls, self.file_visited.open('wb') as f_visited:
            pickle.dump(self.urls, f_urls, pickle.HIGHEST_PROTOCOL)
            pickle.dump(self.explored, f_visited, pickle.HIGHEST_PROTOCOL)

    def _download(self, url, page, containers):
        title = page.find('title')
        parent_tag, attrs = containers[0]
        contents = page.find_all(parent_tag, attrs=attrs)
        if contents:
            child_tag, attr_child = containers[1]
            for content in contents:
                targets = content.find_all(child_tag, attrs=attr_child)
                if targets:
                    self.save(url, targets, title, attr_child)

    def save(self, url, targets, title, attr):
        raise NotImplemented


class ImageCrawler(Crawler):

    def save(self, url, srcs, title, attr):
        hostname = urlparse(url).hostname
        with requests.session() as session:
            for src in srcs:
                self._save_one(session, url, src, attr, hostname)

    def _save_one(self, session, url, src, attr, hostname):
        src, p = self._pre_process(src, attr, hostname)
        if not p.exists():
            self._get(session, src, url, self._write, p)

    def _pre_process(self, src, attr, hostname):
        if isinstance(src, element.Tag):
            src = src[list(attr)[0]]
        u = urlparse(src)
        src = self._parse_url(u, hostname)
        p = Path(self.root, u.netloc, u.path.lstrip('/'))
        return src, p

    def _write(self, resp, p):
        p.parent.mkdir(parents=True, exist_ok=True)
        print(f'Writing image to {p}')
        p.write_bytes(resp.content)


class TextCrawler(Crawler):

    def save(self, url, paras, title, attr):

        path, contents = self._pre_process(url, paras, title)
        if contents:
            self._write(path, contents)

    def _pre_process(self, url, contents, title):
        u = urlparse(url)
        illegal_characters = r'<>:"/\|?*'
        name = title.text.split('-')[0]
        for ic in illegal_characters:
            name = name.replace(ic, '')
        p = (Path(self.root, u.netloc, u.path.lstrip('/')).parent / name).with_suffix('.txt')
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            contents = '\n    '.join(para.text for para in contents)
            contents = f'# {name}\n\n    {contents}'
            return p, contents

    def _write(self, path, contents):
        print(f'Saving {path.stem} to {path}')
        path.write_text(contents, encoding='utf-8')


class CrawlerMultiThread(Crawler):

    def __init__(self, url, root, max_workers=5, attempt=3, timeout=(3, 5), verify=False):
        super().__init__(url, root, attempt=attempt, timeout=timeout, verify=verify)
        self.max_workers = max_workers

    def crawl(self, containers):
        while self.urls:
            ttl = len(self.urls)
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                with requests.session() as session:
                    if ttl < self.max_workers:
                        futures = [executor.submit(self._crawl_one, session, self.urls.pop(), containers)
                                   for _ in range(ttl)]
                    else:
                        futures = [executor.submit(self._crawl_one, session, self.urls.pop(), containers)
                                   for _ in range(self.max_workers)]
                        while self.urls:
                            for future in as_completed(futures):
                                url = self.urls.pop()
                                f = executor.submit(self._crawl_one, session, url, containers)
                                futures.remove(future)
                                futures.append(f)

    def _distill(self, url, page, containers):
        with ThreadPoolExecutor() as executor:
            executor.submit(self._update_links, url, page)
            executor.submit(self._download, url, page, containers=containers)


class ImageCrawlerMultiThread(CrawlerMultiThread, ImageCrawler):

    def save(self, url, srcs, title, attr):
        hostname = urlparse(url).hostname
        with ThreadPoolExecutor() as executor:
            with requests.session() as session:
                [executor.submit(self._save_one, session, url, src, attr, hostname) for src in srcs]


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
