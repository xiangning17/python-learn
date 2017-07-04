# coding: utf-8
import redis
import urlparse

import requests

from bs4 import BeautifulSoup


# r = redis.Redis(host='127.0.0.1', port=6379)

HOST = "http://172.26.35.223"


class InternalSpider(object):
    def __init__(self, start_url, max_layer=1):

        self._max_layer = max_layer

        parsed = urlparse.urlparse(start_url)
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
        self.get_url(self._url, 1)
        pass

    def get_url(self, url, layer):

        # 保存
        print 'save %d layer url:%s' % (layer, url)

        if layer > self._max_layer:
            return

        pass

        session = self._session
        # session = requests.Session()
        rsp = session.get(url)

        path = urlparse.urlparse(rsp.url).path
        if path == '/redmine/login':    # 登陆
            payload = {'username': 'ning.xiang', 'password': 'zaq!@#xsw123'}
            rsp = session.post(rsp.url, data=payload)
            url = rsp.url

        if not rsp.ok:
            # logging error
            print 'response error!'
            return

        bs = BeautifulSoup(rsp.text, "html.parser")

        all_link = bs.select('a[href]')
        for a in all_link:
            in_url = self.parse_internal_url(url, a['href'])
            if in_url:
                self.get_url(in_url, layer + 1)
            else:
                print "filter link:%s" % a['href']

    def parse_internal_url(self, parent_url, url):
        print 'parse internal url, parent=%s, url=%s' % (parent_url, url)
        parse = urlparse.urlparse(url)
        netloc = parse.netloc
        path = parse.path

        if netloc == '':  # 内链
            if path == '':    # 页内跳转
                return None
            elif path.startswith('/'):  # 根路径
                return urlparse.urlunparse(parse._replace(scheme=self._scheme, netloc=self._netloc))
                pass
            else:                       # 相对路径
                return urlparse.urljoin(parent_url, path)
                pass
        elif netloc != self._netloc:
            return None
        else:
            return url


def main():
    # proxies = {
    #     "http": "http://172.26.35.84:808",
    #     "https": "https://172.26.35.84:808",
    # }

    s = requests.Session()
    # s.auth = ("ning.xiang", "zaq!@#xsw123")

    r = s.get('http://172.26.35.223/redmine/projects/integration/wiki', allow_redirects=True)
    # r = s.get('http://172.26.35.223/redmine/login?back_url=http%3A%2F%2F172.26.35.223%2Fredmine%2Fprojects%2Fintegration%2Fwiki', allow_redirects=True)
    # r = requests.get('http://172.26.35.223/redmine/projects/integration/wiki', allow_redirects=True)

    parsed = urlparse.urlparse(r.url)
    print r.url, parsed.path
    print r.history, r.is_redirect
    print "======================="

    if parsed.path.strip().endswith("login"):
        payload = {'username': 'ning.xiang', 'password': 'zaq!@#xsw123'}
        r = s.post(r.url, data=payload)

    parsed = urlparse.urlparse(r.url)
    print r.url, parsed.path
    print r.history, r.is_redirect

    print r.status_code, r.cookies
    print r.headers

    print r.text


if __name__ == '__main__':
    # main()
    InternalSpider("http://172.26.35.223/redmine/projects/integration/wiki").start()
