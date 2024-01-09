import pickle
from urllib.parse import urlparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from bs4 import BeautifulSoup, element
import httpx
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt

from coloredlogger import coloredlogger

logger = coloredlogger(__name__)


class Crawler:

    attempt = 3

    def __init__(self, url, root, *, limits=100, timeout=5, **kwargs):

        u = urlparse(url)
        if u.scheme == '':
            u = u._replace(scheme='https')
        url = u.geturl()
        self.root = root
        self.domain = u.netloc
        self.file_urls = Path(self.domain).with_suffix('.url.pickle')
        self.file_visited = Path(self.domain).with_suffix('.visited.pickle')
        self.limits = httpx.Limits(max_connections=limits,
                                   max_keepalive_connections=limits // 5,
                                   keepalive_expiry=5.0)
        self.session = httpx.Client(limits=self.limits,
                                    timeout=httpx.Timeout(timeout=timeout),
                                    **kwargs)

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
            self._crawl_one(url, containers)

    def _crawl_one(self, url, containers):

        logger.info('Crawling %s, total %d, finished %d', url, len(self.urls), len(self.explored))
        self.explored.add(url)
        page = self._get(url, url, self._parse_html)
        if page:
            self._distill(url, page, containers)

    def _parse_html(self, resp):
        return BeautifulSoup(resp.text, 'html.parser')

    def _distill(self, url, page, containers):
        # update links in current page
        self._update_links(url, page)

        # get specified contents
        self._post_process(url, page, containers)

    @retry(stop=stop_after_attempt(attempt))
    def _get(self, url, ori_url, f, *args):
        self.session.headers = {'User-Agent': UserAgent().random,
                                "Accept-Encoding": "*",
                                "Connection": "keep-alive"
                                }
        try:
            r = self.session.get(url)
            r.raise_for_status()
        except Exception as e:
            logger.exception('%s happens %s', url, e)
            # if error, restore unfinished url
            self._restore_url(ori_url)
        else:
            r.encoding = 'utf-8'
            return f(r, *args)

    def _update_links(self, url, page):
        hostname = urlparse(url).netloc
        links = page.find_all('a', href=True)
        for link in links:
            href = link['href']
            u = urlparse(href)
            if u.netloc != '' and u.netloc != hostname or u.scheme == 'javascript':
                continue
            href = self._parse_url(u, hostname)
            if href not in self.explored:
                self.urls.add(href)

    def _parse_url(self, parsed_url, hostname):
        if parsed_url.scheme == '':
            parsed_url = parsed_url._replace(scheme='https')
        if parsed_url.netloc == '':  # convert relative url to absolute url
            parsed_url = parsed_url._replace(netloc=hostname)
        parsed_url = parsed_url._replace(params='', query='', fragment='')
        return parsed_url.geturl()

    def _restore_url(self, url):
        self.urls.add(url)
        self.explored.discard(url)

    def store(self):
        with self.file_urls.open('wb') as f_urls, self.file_visited.open('wb') as f_visited:
            pickle.dump(self.urls, f_urls, pickle.HIGHEST_PROTOCOL)
            pickle.dump(self.explored, f_visited, pickle.HIGHEST_PROTOCOL)

    def _post_process(self, url, page, containers):
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
        for src in srcs:
            self._save_one(url, src, attr, hostname)

    def _save_one(self, url, src, attr, hostname):
        src, p = self._pre_prepare(src, attr, hostname)
        if not p.exists():
            self._get(src, url, self._write, p)

    def _pre_prepare(self, src, attr, hostname):
        if isinstance(src, element.Tag):
            src = src[list(attr)[0]]
        u = urlparse(src)
        src = self._parse_url(u, hostname)
        p = Path(self.root, u.netloc, u.path.lstrip('/'))
        return src, p

    def _write(self, resp, p):
        p.parent.mkdir(parents=True, exist_ok=True)
        logger.info('Writing image to %s', p)
        p.write_bytes(resp.content)


class TextCrawler(Crawler):

    def save(self, url, paras, title, attr):

        path, contents = self._pre_prepare(url, paras, title)
        if contents:
            self._write(path, contents)

    def _pre_prepare(self, url, contents, title):
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
        logger.info('Saving %s to %s', path.stem, path)
        path.write_text(contents, encoding='utf-8')


class CrawlerMultiThread(Crawler):

    def __init__(self, url, root, max_workers=5, **kwargs):
        super().__init__(url, root, **kwargs)
        self.max_workers = max_workers

    def crawl(self, containers):
        while self.urls:
            ttl = len(self.urls)
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                if ttl < self.max_workers:
                    futures = [executor.submit(self._crawl_one, self.urls.pop(), containers)
                               for _ in range(ttl)]
                else:
                    futures = [executor.submit(self._crawl_one, self.urls.pop(), containers)
                               for _ in range(self.max_workers)]
                try:
                    while self.urls:
                        for future in as_completed(futures):
                            url = self.urls.pop()
                            f = executor.submit(self._crawl_one, url, containers)
                            futures.remove(future)
                            futures.append(f)
                except KeyboardInterrupt:
                    logger.warning('Caught KeyboardInterrupt, stopping crawler now')
                    break

    def _distill(self, url, page, containers):
        with ThreadPoolExecutor() as executor:
            executor.submit(self._update_links, url, page)
            executor.submit(self._post_process, url, page, containers)


class ImageCrawlerMultiThread(CrawlerMultiThread, ImageCrawler):

    def save(self, url, srcs, title, attr):
        hostname = urlparse(url).hostname
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            [executor.submit(self._save_one, url, src, attr, hostname) for src in srcs]


class TextCrawlerMultiThread(CrawlerMultiThread, TextCrawler):

    pass


def main(Krawler, url, root, containers, **kwargs):
    crawler = Krawler(url, root, **kwargs)
    try:
        crawler.crawl(containers)
    finally:
        crawler.session.close()
        crawler.store()
        logger.info('Remaining %d  finished %d', len(crawler.urls), len(crawler.explored))


if __name__ == '__main__':
    pass
