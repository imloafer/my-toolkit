import pickle
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlunparse
from pathlib import Path

from bs4 import BeautifulSoup, element
import urllib3
import requests
from requests.adapters import HTTPAdapter
from fake_useragent import UserAgent

from crawler import Crawler, ImageCrawler, TextCrawler, main

# suppress waring messages
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


if __name__ == '__main__':
    pass
