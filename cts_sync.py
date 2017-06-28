#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pprint
import urllib
from collections import namedtuple
from functools import partial
from time import *
from urlparse import urlparse

import logging

from bs4 import BeautifulSoup

import os

from datetime import datetime
# from tomorrow import threads 另一种多线程执行

HOST = "http://172.26.35.223"
LOCAL_DIR = "/data/Project/tmp"


FileStruct = namedtuple("FileStruct", ("is_dir", "url", "name", "modify_time"))

LOG_FORMAT = '%(asctime)s - %(filename)s[line:%(lineno)d] - %(threadName)s - %(levelname)s: %(message)s'
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)
file_handler = None


def get_file_logging_handler(filename):
    fh = logging.FileHandler(os.path.join(LOCAL_DIR, filename))
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    return fh


def cts_sync():
    global file_handler
    logger = logging.getLogger()
    logger.removeHandler(file_handler)
    file_handler = get_file_logging_handler(str(datetime.now()) + ".log")
    logger.addHandler(file_handler)

    sync_dir(HOST + "/cts/Soul35_VF/")

    file_handler.flush()


from MultiThreadExecutor import MultiThreadExecutor
mte = MultiThreadExecutor(20)


@mte.async
def sync_dir(url):

    ps = urlparse(url)

    path_local = unicode(urllib.unquote(str(ps.path)), "utf-8")     # 从url转化为路径形式，具体为“urlencode -> utf-8 -> unicode”
    path_local = LOCAL_DIR + path_local
    logging.debug("sync dir %s, path = %s" % (url, path_local))

    if not os.path.exists(path_local):   # 若本地不存在该目录，则创建
        os.makedirs(path_local)

    html = urllib.urlopen(url)
    bs = BeautifulSoup(html, "html.parser")
    rows = bs.select("table tr")

    parse_row = partial(_parse_row, url=url, path_local=path_local)
    files = map(parse_row, rows[3:-1])      # 解析Tag， 返回FileStruct列表

    require_update = filter(update, files)  # 得到需要更新的文件（文件夹总是在返回结果中，因为还需要判断其中的文件是否有更新）
    logging.debug("%s require_update %d:\n%s " % (path_local, len(require_update), pprint.pformat(require_update)))

    for f in require_update:
        if f.is_dir:
            sync_dir(f.url)
        else:
            download(f)

    return FileStruct(True, "finish sync %s" % url, "name", "time")


def _parse_row(tag, url, path_local):
    """解析一行代表文件/文件夹的“td”标签"""
    is_dir = False

    children = tag.children

    img = next(children).img
    if img.attrs["alt"] == "[DIR]":
        is_dir = True

    a = next(children).a
    url = os.path.join(url, a.attrs["href"])    # 构造全完整url

    name = os.path.join(path_local, a.text)

    modify_time = next(children).text.strip()   # 去除字符串前后空格
    modify_time = int(mktime(strptime(modify_time, "%d-%b-%Y %H:%M")))  # 转换时间字符串为time整数, 原格式为“12-May-2016 18:45”

    # logging.debug("FileStruct : " + str((is_dir, url, name, modify_time),))
    return FileStruct(is_dir, url, name, modify_time)


def update(f):
    """根据给出的FileStruct判断是否需要更新本地的文件（夹），
    当文件（夹）不存在或者当前FileStruct代表的是文件夹亦或是文件的修改时间与FileStruct中修改时间不一致时返回True，即为需要修改"""
    return not os.path.exists(f.name) or os.path.isdir(f.name) or os.path.getmtime(f.name) != f.modify_time


@mte.async
def download(file_struct):
    urllib.urlretrieve(file_struct.url, file_struct.name)   # 下载文件
    os.utime(file_struct.name, (file_struct.modify_time, file_struct.modify_time))     # 设置文件的修改时间为网站上获取到的时间
    logging.debug("finished download %s from %s" % (file_struct.name, file_struct.url))

if __name__ == '__main__':
    start = time()
    cts_sync()
    # mte.start()
    # mte.join()

    end = time()
    print "Time: %f seconds" % (end - start)
    logging.debug("finish sync cts from server!")
