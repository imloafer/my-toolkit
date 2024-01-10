# crawler.py

  a tool to crawl picture or text from website. it is extendable by subclass certain class.

it includes:

- class *Crawler*

  base class for crawling, cannot use directly.

- class *ImageCrawler*
  
  class for crawling images sequentially, inherit from Crawler.

- class *TextCrawler*

  class for crawling text sequentially, inherit from Crawler.

- class *CrawlerMultiThread*

  base class for multithread crawling, inherit from Crawler, cannot use directly.

- class *ImageCrawlerMultiThread*

  class for multithread (concurrently) crawling pictures, inherit from CrawlerMultiThread and ImageCrawler.

- class *TextCrawlerMultiThread*

  class for multithread (concurrently) crawling text, inherit from CrawlerMultiThread and TextCrawler.

- class *CrawlerAsync*

  base class for asynchronously crawling, inherit from Crawler, cannot use directly.

- class *ImageCrawlerAsync*

  class for asynchronously crawling pictures, inherit from CrawlerAsync and ImageCrawler.

- class *TextCrawlerAsync*

  class for asynchronously crawling text, inherit from CrawlerAsync and TextCrawler.

- function *main*

  you can instance certain class according your need. *main* function supplies a simple and composed way, you just need to pass certain class and parameters to it, it will do all next.

## parameters

- *root:* the root directory which your pictures or text files will be stored.
- *url:* the url that you want to crawl, if this url crawled before, will restore from saved data and start from arbitary url in database.
- *containers:* to locate the content which you want to crawl. default it is a list with **2** groups of tuple. such as: `containers = [('div', {'id': 'picg'}), ('img', {'src': True})]`
- *max_workers:* (for multithread only), pass max threading, default is **5**.
- *max_coco:* (for async only), pass max corotine. meanwhile if max_coco is larger than limits, limits will use max_coco. default is **100**.
- *timer:* (for async only), a tuple, for example (120, 10) means run 120 seconds and then pause 10 seconds, because async is really fast, to reduce sever's load, it is better to pause a while. default is **(60, 10)**.
- *limits:* parameter pass to httpx, means max connections in a connection pool, default is **100**.
- *timeout:* parameter pass to httpx, default is **5** seconds.
- **kwargs:* other parameters pass to httpx.

## How to use

simple way is to use *main* function, pass proper parameters to it.

for example:

```python
from pathlib import Path

from crawler import ImageCrawlerAsync

if __name__ == '__main__':
  ROOT = Path(r'E:/test')
  MAX_COCO = 50
  url = 'https://www.example.com'
  containers = [('div', {'class': 'content'}), ('img', {'src': True})]
  main(ImageCrawlerAsync, url, ROOT, containers,
       max_coco=MAX_COCO,
       timer=(120, 5),
       timeout=10,
       follow_redirects=True)
```

```python
from pathlib import Path

from crawler import TextCrawlerMultiThread

if __name__ == '__main__':
  root = Path(r'E:/test')
  max_workers = 5
  url = 'https://www.sample.com'
  containers = [('div', {'class': 'post-content'}), ('p', {})]
  main(TextCrawlerMultiThread, url, root, containers,
       max_workers=max_workers
       timeout=5,
       follow_redirects=True)

```
