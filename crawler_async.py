from urllib.parse import urlparse
import asyncio
from pathlib import Path

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
                if ttl < self.max_coco + 1:
                    to_do = [self._crawl_one(session, url, containers)
                             for _ in range(ttl) if (url := self.urls.pop()) not in self.explored]
                else:
                    to_do = [self._crawl_one(session, url, containers)
                             for _ in range(self.max_coco + 1) if (url := self.urls.pop()) not in self.explored]
                await asyncio.gather(*to_do)
                # for td in asyncio.as_completed(to_do):
                #    print(f'{td} is done')

    async def _crawl_one(self, session, url, containers):

        print(f'Crawling {url}, total {len(self.urls)}, finished {len(self.explored)}')
        page = await self._get(session, url, url, self._parse_html)
        if page:
            await asyncio.gather(self._update_links(url, page),
                                 self._download(url, page, containers=containers))

    # @retry(stop=stop_after_attempt(3))
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
            print(f'url {url} happens {e}')
            # if error, restore unfinished url
            self.urls.add(ori_url)
        else:
            r.encoding = 'utf-8'
            self.explored.add(ori_url)
            return await f(r, *args)

    async def _parse_html(self, resp):
        return super()._parse_html(resp)

    async def _update_links(self, url, page):
        super()._update_links(url, page)

    async def _download(self, url, page, containers):
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
        src, p = self._pre_process(src, attr, hostname)
        if not p.exists():
            await self._get(session, src, url, self._write, p)

    async def _write(self, resp, p):
        await asyncio.to_thread(super()._write, resp, p)


class TextCrawlerAsync(CrawlerAsync, TextCrawler):

    async def save(self, url, paras, title, attr):
        path, contents, name = self._pre_process(url, paras, title)
        if contents:
            await asyncio.to_thread(self._write, path, contents, name, url)


def main(Krawler, url, root, containers, **kwargs):
    crawler = Krawler(url, root, **kwargs)
    try:
        asyncio.run(crawler.crawl(containers))
    finally:
        crawler.store()


if __name__ == '__main__':
    root = Path(r'E:\test')
    url = 'https://www.meitule.net'
    containers = [('div', {'class': 'content'}), ('img', {'src': True})]
    main(ImageCrawlerAsync, url, root, containers, max_coco=99, timeout=10)
