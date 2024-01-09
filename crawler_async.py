from urllib.parse import urlparse
import asyncio
import time

import httpx
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt

from crawler import Crawler, ImageCrawler, TextCrawler
from coloredlogger import coloredlogger

logger = coloredlogger(__name__)


class CrawlerAsync(Crawler):

    attempt = 3

    def __init__(self, url, root, *, limits=100, timeout=5, timer=(60, 10), max_coco=100, **kwargs):
        super().__init__(url, root, limits=limits, timeout=timeout, **kwargs)
        self.timer = timer
        if max_coco > limits:
            self.limits = httpx.Limits(max_connections=max_coco,
                                       max_keepalive_connections=max_coco // 5,
                                       keepalive_expiry=5.0)
        self.max_coco = max_coco
        self.session = httpx.AsyncClient(limits=self.limits,
                                         timeout=httpx.Timeout(timeout=timeout),
                                         **kwargs)

    async def crawl(self, containers):
        start = time.time()
        cycle_time, pause_time = self.timer
        while self.urls:
            ttl = len(self.urls)
            if ttl < self.max_coco:
                pending = {asyncio.create_task(self._crawl_one(self.urls.pop(), containers))
                           for _ in range(ttl)}
            else:
                pending = {asyncio.create_task(self._crawl_one(self.urls.pop(), containers))
                           for _ in range(self.max_coco)}
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

        logger.info('Crawling %s, total %d, finished %d', url, len(self.urls), len(self.explored))
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

    async def save(self, url, targets, title, attr):
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


def main_async(Krawler, url, root, containers, **kwargs):
    crawler = Krawler(url, root, **kwargs)
    try:
        asyncio.run(crawler.crawl(containers))
    finally:
        crawler.store()
        logger.info('Remaining %d  finished %d', len(crawler.urls), len(crawler.explored))


if __name__ == '__main__':
    pass
