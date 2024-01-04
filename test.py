import asyncio
import time
from pathlib import Path
import pickle

from bs4 import BeautifulSoup, element
import urllib3
import requests
from fake_useragent import UserAgent


def _get(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    resp = requests.get(url, headers=headers, timeout=6)
    print(resp)
    resp.close()

def crawl_one(url):

    print(f'Crawling {url}')
    _get(url)
    # response.raise_for_status()


def main():
    # with open('pic.ccav.url.pickle', 'rb') as f:
    #     urls = pickle.load(f)

    urls = ['https://pic.ccav.co/album/100879.html', 'https://cdn.ccav.co/pic/album/202401/809185/29156216.webp'] #list(urls)[:5]
    for url in urls:
        crawl_one(url)


async def add(a, b):
    await asyncio.sleep(3)
    return a + b


async def delay(sec):
    print(f'I am sleeping for {sec} seconds')
    await asyncio.sleep(sec)
    print(f'I woke up after {sec} seconds')


def long():
    c = 2
    for _ in range(100000000):
        c += 1
    print(f'c = {c}')
    return c


async def main1():
    start = time.time()
    # loop = asyncio.get_running_loop()
    task2 = asyncio.create_task(asyncio.to_thread(long))
    # result1 = await asyncio.to_thread(long)
    task = asyncio.create_task(add(2, 3))
    task1 = asyncio.create_task(delay(2))
    result = await task
    await task1
    result1 = await task2

    print(f'result is {result}')
    print(f'long is {result1}')
    end = time.time()
    print(end - start)

if __name__ == '__main__':
    asyncio.run(main1())