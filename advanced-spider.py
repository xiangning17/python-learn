# coding: utf-8
import redis
from urlparse import urlparse, urlunparse, urljoin
from time import time

import requests
from bs4 import BeautifulSoup

import logging

from AsyncExecutor import async

# 连接redis服务器
r = redis.Redis(host='127.0.0.1', port=6379)
r.flushall()

HOST = "http://172.26.35.223"


LOG_FORMAT = '%(asctime)s - %(filename)s[line:%(lineno)d] - %(threadName)s - %(levelname)s: %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

INTERNAL_URL = 'internal_url'


class InternalSpider(object):

    def __init__(self, start_url, max_layer=1):

        self._max_layer = max_layer

        parsed = urlparse(start_url)
        scheme = parsed.scheme
        netloc = parsed.netloc

        if scheme == '' or netloc == '':
            raise ValueError("url not contain a protocol or netloc name")

        self._url = start_url
        self._scheme = scheme
        self._netloc = netloc

        self._session = None

    def start(self):
        self._session = requests.Session()
        logging.info('start from %s' % self._url)
        self.get_url(self._url, 1)

    @async(15)
    def get_url(self, url, layer):
        # 保存
        logging.info('save %d layer url:%s' % (layer - 1, url))
        succeed = r.sadd(INTERNAL_URL, url)      # 添加到redis的集合中

        if not succeed:
            logging.info('duplicate %d layer url:%s' % (layer - 1, url))
            return

        if layer > self._max_layer:
            return

        # 解析网页，提取链接
        session = self._session
        rsp = session.get(url)

        path = urlparse(rsp.url).path
        if path == '/redmine/login':    # 登陆认证
            payload = {'username': 'ning.xiang', 'password': 'zaq!@#xsw123'}
            rsp = session.post(rsp.url, data=payload)
            url = rsp.url

        if not rsp.ok:
            # logging error
            logging.info('response error!')
            return

        bs = BeautifulSoup(rsp.text, "html.parser")

        all_link = bs.select('a[href]')
        for a in all_link:
            in_url = self.parse_internal_url(url, a['href'])
            if in_url:
                self.get_url(in_url, layer + 1)
            else:
                logging.info("filter link:%s" % a['href'])

    def parse_internal_url(self, parent_url, url):
        logging.info('parse internal url, parent=%s, url=%s' % (parent_url, url))
        parse = urlparse(url)
        netloc = parse.netloc
        path = parse.path

        if netloc == '':  # 内链
            if path == '':    # 页内跳转
                return None
            elif path.startswith('/'):  # 根路径
                return urlunparse(parse._replace(scheme=self._scheme, netloc=self._netloc))
            else:                       # 相对路径
                return urljoin(parent_url, path)
        elif netloc != self._netloc:
            return None
        else:
            return url


def main():
    s = time()
    spider = InternalSpider("http://172.26.35.223/redmine/projects/integration/wiki", 2)
    spider.start()
    spider.get_url.join()
    logging.info(time() - s)

    logging.info('saved %d urls!' % r.scard(INTERNAL_URL))


if __name__ == '__main__':
    main()
