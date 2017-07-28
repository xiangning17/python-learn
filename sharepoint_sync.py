# coding: utf-8

import logging
import re
import urlparse
from collections import namedtuple
from os.path import join, splitext, dirname
from tempfile import TemporaryFile

from bs4 import BeautifulSoup
from easywebdav import connect
from requests import Session
from requests_ntlm import HttpNtlmAuth

import redis

from time import time
from AsyncExecutor import async
from threading import local

LOG_FORMAT = '%(asctime)s - %(filename)s[line:%(lineno)d] - %(threadName)s - %(levelname)s: %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

FileStruct = namedtuple('FileStruct', ('is_dir', 'name', 'url'))

r = redis.Redis(host='127.0.0.1', port=6379)
REDIS_KEY_SP_FILES = 'share_point_files'


def exception_handler(e, f, instance, name, url):
    """异常处理器，若某个任务发生异常，则重新同步该任务"""
    logging.error('[exception_handler] : %s for %s(%s, %s)' % (e.message, f.__name__, name.encode('utf-8'), url.encode('utf-8')))
    if f.__name__ == 'sync_dir':
        instance.sync_dir(name, url)
    elif f.__name__ == 'sync_file':
        instance.sync_file(name, url)


class SharePointSync(object):
    def __init__(self, url):
        # 只取schem和netloc两项以便后续构造完整url
        self._url_split = urlparse.urlsplit(url)._replace(path='', query='', fragment='')
        logging.info('init self._url_split : %s' % str(self._url_split))

        self._folder_query_pattern = re.compile(r'^/.+\.aspx\?RootFolder=.+&FolderCTID=.+&View={.+}$')
        self._viewable_file_query_pattern = re.compile(r'^http://.+/_layouts/\w+.aspx\?.*[iI]d=([^&]+).*&DefaultItemOpen=1$')

        self._tlocal = local()

    @async(8, exception_handler)
    def sync_dir(self, name, url):

        logging.info('sync dir [%s] from %s' % (name, url))
        session = self.get_session()
        rsp = session.get(url)

        bs = BeautifulSoup(rsp.content, 'lxml')
        tags = bs.select('div[field=LinkFilename] a')
        files = [self.process_div(tag, name) for tag in tags]   # 对每一行进行处理，获取FileStruct列表

        for f in files:
            if f.is_dir:
                self.sync_dir(f.name, f.url)
            else:
                self.sync_file(f.name, f.url)

    @async(10, exception_handler)
    def sync_file(self, name, url):
        """同步文件到本地临时文件，然后上传到next cloud"""

        logging.info('sync file %s from %s' % (name, url))

        name = name.encode('utf-8')  # easywebdav不支持unicode,需转换为utf-8

        web_dav = self.get_web_dav()
        if web_dav.exists(name):
            return

        with TemporaryFile() as f:
            rsp = self.get_session().get(url, stream=True)

            for content in rsp.iter_content(1024*8):    # 下载
                if content:
                    f.write(content)

            f.seek(0)       # 移动文件指针至0，以供上传

            dir_name = dirname(name)
            if not web_dav.exists(dir_name):
                web_dav.mkdirs(dir_name)

            logging.info('upload file %s' % name)
            web_dav.upload(f, name)       # 上传

            r.sadd(REDIS_KEY_SP_FILES, name)    # 记录成功上传的文件

    def process_div(self, tag, dir_name):
        is_dir = False
        name = join(dir_name, tag.text)
        url = tag['href']
        # 暂时发现三种类型url
        # 1. 文件夹(相对根路径) ： /xxx/Forms/AllItems.aspx?RootFolder=xxx&FolderCTID=xxx&View={xxx}
        # 2. 文件(相对根路径)   ： /xxx/.../xxx/xxx.pdf
        # 3. 可在网页端打开的文件，如ppt、word：
        # http://sps2010.cn.ta-mp.com:8089/_layouts/PowerPoint.aspx?PowerPointView=ReadingView&PresentationId=/TCL%20Research%20Joint%20Lab/ARCHITECTURE/Test%20Cloud/TCL%20Test%20Matrix_V0.3.pptx&Source=http%3A%2F%2Fsps2010%2Ecn%2Eta%2Dmp%2Ecom%3A8089%2FTCL%2520Research%2520Joint%2520Lab%2FForms%2FAllItems%2Easpx%3FRootFolder%3D%252FTCL%2520Research%2520Joint%2520Lab%252FARCHITECTURE%252FTest%2520Cloud&DefaultItemOpen=1&DefaultItemOpen=1
        # http://sps2010.cn.ta-mp.com:8089/_layouts/WordViewer.aspx?id=/TCL%20Research%20Joint%20Lab/ARCHITECTURE/Blur%20Framework/TN_BLUR_FRAMEWORK_API_v0.1.doc&Source=http%3A%2F%2Fsps2010%2Ecn%2Eta%2Dmp%2Ecom%3A8089%2FTCL%2520Research%2520Joint%2520Lab%2FForms%2FAllItems%2Easpx%3FRootFolder%3D%252FTCL%2520Research%2520Joint%2520Lab%252FARCHITECTURE%252FBlur%2520Framework%26InitialTabId%3DRibbon%252EDocument%26VisibilityContext%3DWSSTabPersistence&DefaultItemOpen=1&DefaultItemOpen=1

        if self._folder_query_pattern.match(url):       # 文件夹
            is_dir = True
        else:                                           # 文件
            # 匹配到在网页端展示的文件（一般来说该链接是网页加载后js重新生成的，爬虫不会遇到）
            m = self._viewable_file_query_pattern.match(url)
            if m:
                logging.info("get real url['%s'] from viewable file url[%s]" % (m.group(1), url))
                url = m.group(1)

            # 对文件名加上后缀名
            file_ext = splitext(url)[1]  # 获取文件后缀名
            name += file_ext

        return FileStruct(is_dir, name, self.get_full_url(url))

    def get_session(self):
        if not hasattr(self._tlocal, 'session'):
            self._tlocal.session = Session()
            self._tlocal.session.auth = HttpNtlmAuth('ta-cd\\ning.xiang', 'zaq!@#xsw123')

        return self._tlocal.session

    def get_web_dav(self):
        if not hasattr(self._tlocal, 'web_dav'):
            self._tlocal.web_dav = connect('172.26.35.47', 8087, username='sharepoint', password='sharepointadmin', path='/remote.php/webdav')

        return self._tlocal.web_dav

    def get_full_url(self, url):
        if not url.startswith('http'):
            new_url = urlparse.urlunsplit(self._url_split._replace(path=url))
            logging.info("[get_full_url] : convert url from '%s' to '%s'" % (url, new_url))

            url = new_url

        return url


def get_top_dir(sps):
    rsp = sps.get_session().get('http://sps2010.cn.ta-mp.com:8089/SitePages/Forms/AllPages.aspx')
    bs = BeautifulSoup(rsp.content, 'lxml')
    # 通过css选择器选择到包含顶级目录名称与链接的<a>标签
    tags = bs.select('div#ctl00_PlaceHolderLeftNavBar_QuickLaunchNavigationManager div.menu.vertical.menu-vertical ul ul:nth-of-type(2) li a')
    return [(a.span.span.text, sps.get_full_url(a['href'])) for a in tags]


if __name__ == '__main__':
    start = time()

    sp = SharePointSync('http://sps2010.cn.ta-mp.com:8089')

    top_dirs = get_top_dir(sp)
    [sp.sync_dir(join('/SWO(REQ)', dir[0]), dir[1]) for dir in top_dirs[3:5]]

    sp.sync_file.join()

    logging.info('sync file count are %s' % r.scard(REDIS_KEY_SP_FILES))
    end = time()
    logging.info("finish sync swo documents! Spent time : %f seconds" % (end - start))

