from urllib.parse import urlparse
import asyncio

import httpx
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt

from crawler import Crawler, ImageCrawler, TextCrawler


class CrawlerAsync(Crawler):

    def __init__(self, url, root, max_coco=50, attempt=3, timeout=3, verify=False):
        super().__init__(url, root, attempt=attempt, timeout=timeout, verify=verify)
        self.max_coco = max_coco
        self.transport = httpx.AsyncHTTPTransport(retries=self.attempt)

    async def crawl(self, containers):
        while self.urls:
            ttl = len(self.urls)
            async with httpx.AsyncClient(verify=self.verify, transport=self.transport) as session:
                if ttl < self.max_coco:
                    to_do = [asyncio.create_task(self._crawl_one(session, self.urls.pop(), containers))
                             for _ in range(ttl)]
                else:
                    to_do = [asyncio.create_task(self._crawl_one(session, self.urls.pop(), containers))
                             for _ in range(self.max_coco)]
                while to_do and self.urls:
                    done, to_do = await asyncio.wait(to_do, return_when=asyncio.FIRST_COMPLETED)
                    for _ in done:
                        task = asyncio.create_task(self._crawl_one(session, self.urls.pop(), containers))
                        to_do.add(task)

    async def _crawl_one(self, session, url, containers):

        print(f'Crawling {url}, total {len(self.urls)}, finished {len(self.explored)}')
        page = await self._get(session, url, url, self._parse_html)
        if page:
            await asyncio.gather(self._update_links(url, page),
                                 self._post_process(url, page, containers=containers))

    @retry(stop=stop_after_attempt(3))
    async def _get(self, session, url, ori_url, f, *args):
        headers = {'User-Agent': UserAgent().random,
                   "Accept-Encoding": "*",
                   "Connection": "keep-alive"
                   }
        try:
            r = await session.get(url,
                                  headers=headers,
                                  timeout=self.timeout,
                                  follow_redirects=True,)
            r.raise_for_status()
        except KeyboardInterrupt:
            self._restore_url(ori_url)
        except Exception as e:
            print(f'{url} happens {e}')
            # if error, restore unfinished url
            self.urls.add(ori_url)
        else:
            r.encoding = 'utf-8'
            self.explored.add(ori_url)
            loop = asyncio.get_running_loop()
            result = loop.run_in_executor(None, f, r, *args)
            return await result

    async def _update_links(self, url, page):
        super()._update_links(url, page)

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


class ImageCrawlerAsync(CrawlerAsync, ImageCrawler):

    async def save(self, url, srcs, title, attr):
        hostname = urlparse(url).hostname
        async with httpx.AsyncClient(verify=self.verify) as session:
            to_do = [self._save_one(session, url, src, attr, hostname)
                     for src in srcs]
            await asyncio.gather(*to_do)

    async def _save_one(self, session, url, src, attr, hostname):
        src, p = self._pre_prepare(src, attr, hostname)
        if not p.exists():
            await self._get(session, src, url, self._write, p)


class TextCrawlerAsync(CrawlerAsync, TextCrawler):

    async def save(self, url, paras, title, attr):
        path, contents = self._pre_prepare(url, paras, title)
        if contents:
            await asyncio.to_thread(self._write, path, contents)


def main_async(Krawler, url, root, containers, **kwargs):
    crawler = Krawler(url, root, **kwargs)
    try:
        asyncio.run(crawler.crawl(containers))
    finally:
        crawler.store()


if __name__ == '__main__':
    pass
