import pickle
from urllib.parse import urlparse, urlunparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup, element
import httpx
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

            with httpx.Client() as session:
                self._crawl_one(session, url, containers)

    def _crawl_one(self, session, url, containers):
        print(f'Crawling {url}, total {len(self.urls)}, finished {len(self.explored)}')
        response = self._get(session, url, url)
        if response:
            # parse page
            page = self._parse_html(response.text)
            # add visited url to explored set and serialize it.
            self.explored.add(url)
            self._distill(url, page, containers=containers)

    def _parse_html(self, html):
        return BeautifulSoup(html, 'html.parser')

    def _distill(self, url, page, containers):
        # update links in current page
        self._update_links(url, page)

        # download specified contents
        self._download(url, page, containers=containers)

    def _get(self, session, url, ori_url):
        headers = {'User-Agent': UserAgent().random,
                   "Accept-Encoding": "*",
                   "Connection": "keep-alive"
                   }
        try:
            r = session.get(url, headers=headers, timeout=self.timeout, follow_redirects=True)
            r.raise_for_status()
        except KeyboardInterrupt:
            self._restore_url(ori_url)
        except Exception as e:
            print(f'url {url} happens {e}')
            # if error, restore unfinished url
            self._restore_url(ori_url)
        else:
            r.encoding = 'utf-8'
            return r

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

    def save(self, url, targets, title, attr_child):
        raise NotImplemented


class ImageCrawler(Crawler):

    def save(self, url, srcs, title, attr_child):
        hostname = urlparse(url).hostname

        with httpx.Client() as session:
            for src in srcs:
                self._save_one(session, url, src, attr_child, hostname)

    def _save_one(self, session, url, src, attr_child, hostname):
        src, p = self._pre_process(src, attr_child, hostname)
        if not p.exists():
            response = self._get(session, src, url)
            if response:
                self._write(p, src, response)

    def _pre_process(self, src, attr_child, hostname):
        if isinstance(src, element.Tag):
            src = src[list(attr_child)[0]]
        u = urlparse(src)
        src = self._parse_url(u, hostname)
        p = Path(self.root, u.netloc, u.path.lstrip('/'))
        return src, p

    def _write(self, p, src, contents):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(contents.content)
        print(f'Saved image {src}')


class TextCrawler(Crawler):

    def save(self, url, paras, title, attrs_child):

        path, contents, name = self._pre_process(url, paras, title)
        if contents:
            self._write(path, contents, name, url)

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
            return p, contents, name

    def _write(self, path, contents, name, url):
        path.write_text(contents, encoding='utf-8')
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

                with httpx.Client() as session:
                    futures = [executor.submit(self._crawl_one, session, url, containers) for url in urls]
            if (ttl := len(self.urls)) == 0:
                return
        urls = [url for _ in range(self.max_workers+1)
                if (url := self.urls.pop()) not in self.explored]
        while (lng := len(urls)) < self.max_workers and ttl >= (diff := self.max_workers - lng):
            urls += [url for _ in range(diff)
                     if (url := self.urls.pop()) not in self.explored]
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:

            with httpx.Client() as session:
                futures = [executor.submit(self._crawl_one,  session, url, containers) for url in urls]
                while self.urls:
                    for future in as_completed(futures):
                        url = self.urls.pop()
                        f = executor.submit(self._crawl_one, session, url, containers)
                        futures.remove(future)
                        futures.append(f)

    def _distill(self, url, page, containers):
        with ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(self._update_links, url, page)
            executor.submit(self._download, url, page, containers=containers)


class ImageCrawlerMultiThread(CrawlerMultiThread, ImageCrawler):

    def save(self, url, srcs, title, attr_child):
        hostname = urlparse(url).hostname
        with ThreadPoolExecutor() as executor:

            with httpx.Client() as session:
                for src in srcs:
                    executor.submit(self._save_one, session, url, src, attr_child, hostname)


class TextCrawlerMultiThread(CrawlerMultiThread, TextCrawler):

    pass


def main(Krawler, url, root, containers, **kwargs):
    crawler = Krawler(url, root, **kwargs)
    try:
        crawler.crawl(containers)
    finally:
        crawler.store()


if __name__ == '__main__':
    root = Path(r'E:\test')
    url = 'https://www.meitule.net'
    containers = [('div', {'class': 'content'}), ('img', {'src': True})]
    main(ImageCrawlerMultiThread, url, root, containers, max_workers=20, timeout=10)
