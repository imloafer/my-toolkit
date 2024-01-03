import asyncio
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

if __name__ == '__main__':
    main()