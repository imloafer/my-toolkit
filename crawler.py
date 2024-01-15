import pickle
from urllib.parse import urlparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
import time

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
        self.data = Path(self.domain).with_suffix('.dat')
        self.limits = httpx.Limits(max_connections=limits,
                                   max_keepalive_connections=limits // 5,
                                   keepalive_expiry=5.0)
        self.session = httpx.Client(limits=self.limits,
                                    timeout=httpx.Timeout(timeout=timeout),
                                    **kwargs)

        # check if the site crawled before, if then start from arbitrary url.
        try:
            with self.data.open('rb') as f:
                d = pickle.load(f)
                self.urls = d['urls']
                self.explored = d['explored']
        except FileNotFoundError:
            self.urls = {url}
            self.explored = set()

    def crawl(self, containers):

        while self.urls:
            url = self.urls.pop()
            if url in self.explored:
                continue
            self._crawl_one(url, containers)

    def _crawl_one(self, url, containers):

        self._log(url)
        # logger.info('Crawling %s, remain %d, finished %d', url, len(self.urls), len(self.explored))
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
        d = {'urls': self.urls, 'explored': self.explored}
        with self.data.open('wb') as f:
            pickle.dump(d, f, pickle.HIGHEST_PROTOCOL)

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

    def _log(self, url):
        logger.info('Crawling %s, remaining %d, finished %d', url, len(self.urls), len(self.explored))

    def save(self, *args):
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
                    self.session.close()
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


class CrawlerAsync(Crawler):

    attempt = 3

    def __init__(self, url, root, *, limits=100, timeout=5, timer=(60, 10), max_workers=100, **kwargs):
        super().__init__(url, root, limits=limits, timeout=timeout, **kwargs)
        self.timer = timer
        if max_workers > limits:
            self.limits = httpx.Limits(max_connections=max_workers,
                                       max_keepalive_connections=max_workers // 5,
                                       keepalive_expiry=5.0)
        self.max_workers = max_workers
        self.session = httpx.AsyncClient(limits=self.limits,
                                         timeout=httpx.Timeout(timeout=timeout),
                                         **kwargs)

    async def crawl(self, containers):
        start = time.time()
        cycle_time, pause_time = self.timer
        while self.urls:
            ttl = len(self.urls)
            if ttl < self.max_workers:
                pending = {asyncio.create_task(self._crawl_one(self.urls.pop(), containers))
                           for _ in range(ttl)}
            else:
                pending = {asyncio.create_task(self._crawl_one(self.urls.pop(), containers))
                           for _ in range(self.max_workers)}
            try:
                while pending:
                    end = time.time()
                    if cycle_time <= end - start:
                        logger.warning('Taking a %d seconds break', pause_time)
                        time.sleep(pause_time)
                        start = time.time()
                        logger.warning('Continue...')
                    done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                    while done and self.urls:
                        task = asyncio.create_task(self._crawl_one(self.urls.pop(), containers))
                        pending.add(task)
                        done.pop()
            except asyncio.CancelledError:
                await self.aclose()
                await self.session.aclose()
                break

    async def _crawl_one(self, url, containers):

        self._log(url)
        # logger.info('Crawling %s, remain %d, finished %d', url, len(self.urls), len(self.explored))
        self.explored.add(url)
        page = await self._get(url, url, self._parse_html)
        if page:
            await asyncio.gather(asyncio.to_thread(self._update_links, url, page),
                                 self._post_process(url, page, containers))

    @retry(stop=stop_after_attempt(attempt))
    async def _get(self, url, ori_url, f, *args):
        self.session.headers = {'User-Agent': UserAgent().random,
                                "Accept-Encoding": "*",
                                "Connection": "keep-alive"
                                }
        try:
            r = await self.session.get(url)
            r.raise_for_status()
        except Exception as e:
            logger.error('%s happens %s', url, e)
            # if error, restore unfinished url
            self._restore_url(ori_url)
        else:
            r.encoding = 'utf-8'
            result = asyncio.create_task(asyncio.to_thread(f, r, *args))
            return await result

    async def _post_process(self, url, page, containers):
        title = page.find('title')
        parent_tag, attrs = containers[0]
        contents = page.find_all(parent_tag, attrs=attrs)
        if contents:
            child_tag, attr_child = containers[1]
            for content in contents:
                targets = content.find_all(child_tag, attrs=attr_child)
                if targets:
                    await self.save(url, targets, title, attr_child)

    async def save(self, *args):
        raise NotImplemented

    async def aclose(self):
        logger.warning('Hold on, app is finishing remaining tasks...')
        loop = asyncio.get_running_loop()
        tasks = asyncio.all_tasks(loop) - {asyncio.current_task()}
        ttl = len(tasks)
        await asyncio.gather(*tasks)
        logger.warning('Done closing, %d remaining tasks finished', ttl)


class ImageCrawlerAsync(CrawlerAsync, ImageCrawler):

    async def save(self, url, srcs, title, attr):
        hostname = urlparse(url).hostname
        to_do = [self._save_one(url, src, attr, hostname)
                 for src in srcs]
        await asyncio.gather(*to_do)

    async def _save_one(self, url, src, attr, hostname):
        src, p = self._pre_prepare(src, attr, hostname)
        if not p.exists():
            await self._get(src, url, self._write, p)


class TextCrawlerAsync(CrawlerAsync, TextCrawler):

    async def save(self, url, paras, title, attr, **kwargs):
        path, contents = self._pre_prepare(url, paras, title)
        if contents:
            task = asyncio.create_task(asyncio.to_thread(self._write, path, contents))
            await task


def main(Krawler, url, root, containers, **kwargs):
    crawler = Krawler(url, root, **kwargs)
    try:
        if asyncio.iscoroutinefunction(crawler.crawl):
            asyncio.run(crawler.crawl(containers))
        else:
            crawler.crawl(containers)
    finally:
        crawler.store()
        logger.info('Remaining %d  finished %d', len(crawler.urls), len(crawler.explored))


if __name__ == '__main__':
    pass
