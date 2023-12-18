import os
import pickle

from bs4 import BeautifulSoup
from pathlib import Path
import requests
from requests.packages import urllib3
from collections import deque
from tenacity import retry, stop_after_attempt
from modifier import walk


def distill(path):
    path = Path(path)
    for p in walk(path):
        if p.name.endswith(('.html', '.xhtml')):
            with p.open('r', encoding='utf-8') as f:
                page = BeautifulSoup(f.read(), 'html.parser')
                div = page.find('div', {'class': 'post-content'})
                title = page.find('title')
                if div:
                    print('saving...', url, title.text)
                    mode = 'w'
                    # if '?page' in url:
                    #     mode = 'a'
                    save(title, div, path, mode)


def crawl(url, root: [str | Path]):

    urllib3.disable_warnings()  # erase waring messages
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36"}

    domain = url.split('/')[2]
    file_url = Path(domain).with_suffix('.url.pickle')
    file_visited = Path(domain).with_suffix('.visited.pickle')

    # check if this site crawled before, if then start from last end url.
    try:
        with open(file_url, 'rb') as f:
            urls = pickle.load(f)
    except FileNotFoundError:
        urls = deque([url])

    try:
        with open(file_visited, 'rb') as f:
            explored = pickle.load(f)
    except FileNotFoundError:
        explored = set()

    while urls:
        url = urls.popleft()
        if url in explored:
            continue
        try:
            response = get(url, headers=headers, verify=False, timeout=30)
        except Exception:
            urls.appendleft(url)
            break

        # add visited url to explored set and serialize it.
        explored.add(url)
        with open(file_visited, 'wb') as f:
            pickle.dump(explored, f, protocol=pickle.HIGHEST_PROTOCOL)

        # store to different directory depends on web catalogue
        path = Path(root, *url.split('/')[2:-1])
        path.mkdir(parents=True, exist_ok=True)

        # parse page
        page = BeautifulSoup(response.text, 'html.parser')
        links = page.find_all('a', href=True)

        # update page links and serialize it
        urls += deque(sorted([href for link in links
                             if (href := link['href']) not in explored
                             and href.startswith('http')
                             and href.split('/')[2] == domain]))

        with open(file_url, 'wb') as f:
            pickle.dump(urls, f, pickle.HIGHEST_PROTOCOL)

        contents = page.find('div', {'class': 'post-content'})
        title = page.find('title')
        if contents:
            print('saving...', url, title.text)
            mode = 'w'
            # if '?page' in url:
            #     mode = 'a'
            save(title, contents, path, mode)


@retry(stop=stop_after_attempt(3))
def get(url, headers=None, verify=False, timeout=30):
    r = requests.get(url, headers=headers, verify=verify, timeout=timeout)
    r.raise_for_status()
    return r


def save(title, contents, path, mode):
    illegal_characters = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    name = title.text.split('-')[0]
    for ic in illegal_characters:
        name = name.replace(ic, '')
    paras = contents.find_all('p')
    out_path = Path(path, name).with_suffix('.txt')
    with open(out_path, mode=mode, encoding='utf-8') as out:
        out.write(f'# {name}\n\n')
        for p in paras:
            out.write(f'    {p.text}\n')


if __name__ == '__main__':
    root = Path(r'D:\test')
    url = 'https://dwkm.xyz/'
    crawl(url, root)
