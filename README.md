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
- *url:* the root url that you want to crawl, if this url crawled before, will restore from saved data and start from arbitary url in database.
- *containers:* to locate the content which you want to crawl. default it is a list with **2** groups of tuple. such as: `containers = [('div', {'id': 'picg'}), ('img', {'src': True})]`, first one should be the next one's ancestor. if only one group or two more groups, should subclass relevant class and override _post_process method.
- *max_workers:* for multithread, pass max threading, default is **5**. for async, pass max coroutine, if max_workers is larger than limits, limits will use max_workers, default is **100**.
- *redundant:* any extra words in webpage's title which you don't want it, (Webpage's title will be file's name or/and directory's name.) default is None.
- *limits:* parameter pass to [httpx](https://www.python-httpx.org/api/#client), means max connections in a connection pool, default is **100**.
- *timeout:* parameter pass to [httpx](https://www.python-httpx.org/api/#client), default is **5** seconds.
- **kwargs:* other parameters pass to [httpx](https://www.python-httpx.org/api/#client).

## How to use

simple way is to use *main* function, pass proper parameters to it.

for example:

```python
from pathlib import Path

from crawler import ImageCrawlerAsync

if __name__ == '__main__':
  ROOT = Path(r'E:/test')
  MAX_WORKERS = 50
  url = 'https://www.example.com'
  containers = [('div', {'class': 'content'}), ('img', {'src': True})]
  main(ImageCrawlerAsync, url, ROOT, containers,
       max_workers=MAX_WORKERS,
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

or you can instance relevant class by your own:

```python
  from pathlib import Path
  import asyncio

  from clawler import ImageClawlerasync

  root = Path(r'E:/test')
  max_workers = 5
  url = 'https://www.sample.com'
  containers = [('div', {'class': 'post-content'}), ('p', {})]
  clawler = ImageClawlerAsync(url, root)
  try:
    asyncio.run(clawler.clawl(containers))
  finally:
    clawler.store()
```

if you instance by your own, don't forget invoke *store* method to save crawled dat to disk, otherwise it will start from beginning.

## Customization

*catalog(self, html)* method uses to customize crawling contents' catalog depends on website's catalog, pass parsed html to it, subclass *Clawler* and override this method if needs. It constructs part of store path.
*custom_title(self, title)* method use to customize title.subclass *Clawler* and override this method if needs. It constructs part of store path.
