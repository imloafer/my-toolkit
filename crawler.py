import json
from urllib.parse import urlparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio

from bs4 import BeautifulSoup, element
import httpx
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt

from coloredlogger import coloredlogger
from constants import ILLEGAL_CHARACTERS

logger = coloredlogger(__name__)


class Crawler:

    attempt = 3

    def __init__(self, url, root, *, limits=100, timeout=5, **kwargs):

        u = urlparse(url)
        if u.scheme == '':
            u = u._replace(scheme='https')
        url = u.geturl()
        self.domain = u.netloc
        self.root = Path(root, self.domain)
        self.data = Path(self.domain).with_suffix('.json')
        self.limits = httpx.Limits(max_connections=limits,
                                   max_keepalive_connections=limits // 5,
                                   keepalive_expiry=5.0)
        self.session = httpx.Client(limits=self.limits,
                                    timeout=httpx.Timeout(timeout=timeout),
                                    **kwargs)

        # check if the site crawled before, if then start from arbitrary url.
        try:
            with self.data.open('r') as f:
                d = json.load(f)
                self.urls = set(d['urls'])
                self.explored = set(d['explored'])
        except FileNotFoundError:
            self.urls = {url}
            self.explored = set()

    def crawl(self, containers, redundant=None):

        while self.urls:
            url = self.urls.pop()
            if url in self.explored:
                continue
            self._crawl_one(url, containers, redundant)

    def _crawl_one(self, url, containers, redundant):

        self._log(url)
        self.explored.add(url)
        page = self._get(url, url, self._parse_html)
        if page:
            self._preprocess(url, page, containers, redundant)

    def _parse_html(self, resp):
        return BeautifulSoup(resp.text, 'html.parser')

    def _preprocess(self, url, page, containers, redundant):

        self._update_links(url, page)  # update links in current page
        title = self._get_title(page, redundant)  # get title
        targets, child_attr = self._get_target(page, containers)  # get targets
        cat = self.catalog(page)  # get catalog
        store_path = [cat] + title
        if targets:
            self.post_process(url, targets, store_path, child_attr)

    @retry(stop=stop_after_attempt(attempt))
    def _get(self, url, ori_url, f, *args):
        self.session.headers = {'User-Agent': UserAgent().random,
                                "Accept-Encoding": "*",
                                "Connection": "keep-alive"
                                }
        try:
            r = self.session.get(url)
            r.raise_for_status()
        except httpx.RequestError as e:
            logger.error("An error occurred while requesting %s. %s will be restored.",
                         e.request.url, ori_url)
            self._restore_url(ori_url)
        except httpx.HTTPStatusError as e:
            logger.error("Error response %s while requesting %s. %s will be discarded",
                         e.response.status_code, e.request.url, ori_url)
        except Exception as e:
            logger.exception('%s happens %s', url, e)
            # if error, restore unfinished url
            self._restore_url(ori_url)
        else:
            r.encoding = 'utf-8'
            return f(r, *args)

    def _update_links(self, url, page):

        links = page.find_all('a', href=True)
        up = urlparse(url)
        idx = up.path.rfind('/')
        up = up._replace(path=up.path[:idx+1])
        for link in links:
            href = link['href']
            u = urlparse(href)
            if u.netloc == '' and not u.path.startswith('/'):
                u = u._replace(netloc=up.netloc, path=up.path + u.path)
            if (u.netloc != '' and u.netloc != self.domain) or u.scheme == 'javascript':
                continue
            href = self._parse_url(u)
            if href not in self.explored:
                self.urls.add(href)

    def _parse_url(self, parsed_url):
        if parsed_url.scheme == '':
            parsed_url = parsed_url._replace(scheme='https')
        if parsed_url.netloc == '':  # convert relative url to absolute url
            parsed_url = parsed_url._replace(netloc=self.domain)
        parsed_url = parsed_url._replace(params='', query='', fragment='')
        return parsed_url.geturl()

    def _restore_url(self, url):
        self.urls.add(url)
        self.explored.discard(url)

    def store(self):
        d = {'urls': list(self.urls), 'explored': list(self.explored)}
        with self.data.open('w') as f:
            json.dump(d, f)

    def _get_title(self, html, redundant):
        title = html.find('title')
        extras = ' -_.'
        if not title:
            return ['no title']
        title = title.text
        for ic in ILLEGAL_CHARACTERS:
            title = title.replace(ic, '')
        if redundant:
            title = title.replace(redundant, '')
        title = title.strip(extras)
        return self.custom_title(title)

    def custom_title(self, title):
        return [title]

    def _get_target(self, html, containers):
        parent_tag, attrs = containers[0]
        contents = html.find_all(parent_tag, attrs=attrs)
        child_tag, attr_child = containers[1]
        if contents:
            for content in contents:
                targets = content.find_all(child_tag, attrs=attr_child)
                if targets:
                    return targets, attr_child
        return None, attr_child

    def catalog(self, html):
        return ''

    def _log(self, url):
        logger.info('Crawling %s, remaining %d, finished %d', url, len(self.urls), len(self.explored))

    def post_process(self, *args):
        raise NotImplemented


class ImageCrawler(Crawler):

    def post_process(self, url, srcs, store_path, attr):

        for src in srcs:
            self._save(url, src, attr, store_path)

    def _save(self, url, src, attr, store_path):
        src, p = self._pre_prepare(src, attr, store_path)
        if not p.exists():
            self._get(src, url, self._write, p)

    def _pre_prepare(self, src, attr, store_path):
        if isinstance(src, element.Tag):
            src = src[list(attr)[0]]
        u = urlparse(src)
        src = self._parse_url(u)
        name = u.path.split('/')[-1]
        p = Path(self.root, *store_path, name)
        return src, p

    def _write(self, resp, p):
        p.parent.mkdir(parents=True, exist_ok=True)
        logger.info('Writing image to %s', p)
        p.write_bytes(resp.content)


class TextCrawler(Crawler):

    def post_process(self, url, paras, store_path, attr):

        path, contents = self._pre_prepare(paras, store_path)
        if path:
            self._write(path, contents)

    def _pre_prepare(self, contents, store_path):
        p = (Path(self.root, *store_path)).with_suffix('.txt')
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            contents = '\n    '.join(para.text for para in contents)
            contents = f'# {"".join(store_path[1:])}\n\n    {contents}'
            return p, contents
        return None, None

    def _write(self, path, contents):
        logger.info('Saving %s to %s', path.stem, path)
        path.write_text(contents, encoding='utf-8')


class CrawlerMultiThread(Crawler):

    def __init__(self, url, root, max_workers=5, **kwargs):
        super().__init__(url, root, **kwargs)
        self.max_workers = max_workers

    def crawl(self, containers, redundant=None):
        while self.urls:
            ttl = len(self.urls)
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                if ttl < self.max_workers:
                    futures = [executor.submit(self._crawl_one, self.urls.pop(), containers, redundant)
                               for _ in range(ttl)]
                else:
                    futures = [executor.submit(self._crawl_one, self.urls.pop(), containers, redundant)
                               for _ in range(self.max_workers)]
                try:
                    while self.urls:
                        for future in as_completed(futures):
                            url = self.urls.pop()
                            f = executor.submit(self._crawl_one, url, containers, redundant)
                            futures.remove(future)
                            futures.append(f)
                except KeyboardInterrupt:
                    logger.warning('Caught KeyboardInterrupt, stopping crawler now')
                    self.session.close()
                    break

    def _preprocess(self, url, page, containers, redundant):
        with ThreadPoolExecutor(max_workers=3) as executor:
            fs = [executor.submit(self._update_links, url, page),
                  executor.submit(self._get_title, page, redundant),
                  executor.submit(self._get_target, page, containers),
                  executor.submit(self.catalog, page)]
        for f in as_completed(fs):
            res = f.result()
            if isinstance(res, list):
                title = res
            elif isinstance(res, tuple):
                targets, child_attr = res
            elif isinstance(res, str):
                cat = res
        store_path = [cat] + title
        if targets:
            self.post_process(url, targets, store_path, child_attr)


class ImageCrawlerMultiThread(CrawlerMultiThread, ImageCrawler):

    def post_process(self, url, srcs, store_path, attr):

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            [executor.submit(self._save, url, src, attr, store_path) for src in srcs]


class TextCrawlerMultiThread(CrawlerMultiThread, TextCrawler):

    pass


class CrawlerAsync(Crawler):

    attempt = 3

    def __init__(self, url, root, *, limits=100, timeout=5, max_workers=100, **kwargs):
        super().__init__(url, root, limits=limits, timeout=timeout, **kwargs)
        if max_workers > limits:
            self.limits = httpx.Limits(max_connections=max_workers,
                                       max_keepalive_connections=max_workers // 5,
                                       keepalive_expiry=5.0)
        self.max_workers = max_workers
        self.session = httpx.AsyncClient(limits=self.limits,
                                         timeout=httpx.Timeout(timeout=timeout),
                                         **kwargs)

    async def crawl(self, containers, redundant=None):

        while self.urls:
            ttl = len(self.urls)
            if ttl < self.max_workers:
                pending = {asyncio.create_task(self._crawl_one(self.urls.pop(), containers, redundant))
                           for _ in range(ttl)}
            else:
                pending = {asyncio.create_task(self._crawl_one(self.urls.pop(), containers, redundant))
                           for _ in range(self.max_workers)}
            try:
                while pending:
                    done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                    while done and self.urls:
                        task = asyncio.create_task(self._crawl_one(self.urls.pop(), containers, redundant))
                        pending.add(task)
                        done.pop()
            except asyncio.CancelledError:
                await self.aclose()
                await self.session.aclose()
                break

    async def _crawl_one(self, url, containers, redundant):

        self._log(url)
        self.explored.add(url)
        page = await self._get(url, url, self._parse_html)
        if page:
            results = await asyncio.gather(asyncio.to_thread(self._update_links, url, page),
                                           asyncio.to_thread(self._get_title, page, redundant),
                                           asyncio.to_thread(self._get_target, page, containers),
                                           asyncio.to_thread(self.catalog, page))
            _, t, (targets, child_attr), cat = results
            store_path = [cat] + t
            if targets:
                await self.post_process(url, targets, store_path, child_attr)

    @retry(stop=stop_after_attempt(attempt))
    async def _get(self, url, ori_url, f, *args):
        self.session.headers = {'User-Agent': UserAgent().random,
                                "Accept-Encoding": "*",
                                "Connection": "keep-alive"
                                }
        try:
            r = await self.session.get(url)
            r.raise_for_status()
        except httpx.RequestError as e:
            logger.error("An error occurred while requesting %s. %s will be restored.",
                         e.request.url, ori_url)
            self._restore_url(ori_url)
        except httpx.HTTPStatusError as e:
            logger.error("Error response %s while requesting %s.",
                         e.response.status_code, e.request.url)
        except Exception as e:
            logger.error('%s happens %s', url, e)
            # if error, restore unfinished url
            self._restore_url(ori_url)
        else:
            r.encoding = 'utf-8'
            result = asyncio.create_task(asyncio.to_thread(f, r, *args))
            return await result

    async def post_process(self, *args):
        raise NotImplemented

    async def aclose(self):
        logger.warning('Hold on, app is finishing remaining tasks...')
        loop = asyncio.get_running_loop()
        tasks = asyncio.all_tasks(loop) - {asyncio.current_task()}
        ttl = len(tasks)
        await asyncio.gather(*tasks)
        logger.warning('App closed, %d remaining tasks finished', ttl)


class ImageCrawlerAsync(CrawlerAsync, ImageCrawler):

    async def post_process(self, url, srcs, store_path, attr):

        to_do = [self._save(url, src, attr, store_path)
                 for src in srcs]
        await asyncio.gather(*to_do)

    async def _save(self, url, src, attr, store_path):
        src, p = self._pre_prepare(src, attr, store_path)
        if not p.exists():
            await self._get(src, url, self._write, p)


class TextCrawlerAsync(CrawlerAsync, TextCrawler):

    async def post_process(self, url, paras, store_path, attr, **kwargs):

        path, contents = self._pre_prepare(paras, store_path)
        if contents:
            task = asyncio.create_task(asyncio.to_thread(self._write, path, contents))
            await task


def main(Krawler, url, root, containers, redundant=None, **kwargs):
    crawler = Krawler(url, root, **kwargs)
    try:
        if asyncio.iscoroutinefunction(crawler.crawl):
            asyncio.run(crawler.crawl(containers, redundant))
        else:
            crawler.crawl(containers, redundant)
    finally:
        crawler.store()
        logger.info('Remaining %d  finished %d', len(crawler.urls), len(crawler.explored))


if __name__ == '__main__':
    pass
