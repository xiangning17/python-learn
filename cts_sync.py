#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pprint
import urllib
from collections import namedtuple
from functools import partial
from threading import Lock
from time import *
from urlparse import urlparse

from bisect import insort
from jinja2 import Environment, FileSystemLoader, Template

import logging

from bs4 import BeautifulSoup

import os

# from tomorrow import threads 另一种多线程执行

HOST = "http://172.26.35.223"
LOCAL_DIR = "/data/cephfs2"
LOCAL_LOG_DIR = os.path.join(LOCAL_DIR, "cts_log")

FileStruct = namedtuple("FileStruct", ("is_dir", "url", "name", "modify_time"))
FileStruct.__lt__ = lambda x, y: x.name.upper() < y.name.upper()  # 为支持bisect排序

LOG_FORMAT = '%(asctime)s - %(filename)s[line:%(lineno)d] - %(threadName)s - %(levelname)s: %(message)s'
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)
file_handler = None


def get_file_logging_handler(filename):
    fh = logging.FileHandler(os.path.join(LOCAL_LOG_DIR, filename))
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    return fh


def cts_sync():
    global file_handler
    logger = logging.getLogger()
    logger.removeHandler(file_handler)
    file_handler = get_file_logging_handler(strftime('%Y-%m-%d %H:%M:%S') + ".log")
    logger.addHandler(file_handler)

    sync_dir(HOST + "/cts/cts_document/")

    file_handler.flush()


from MultiThreadExecutor2 import MultiThreadExecutor

mte = MultiThreadExecutor(30)


@mte.async
def sync_dir(url):
    ps = urlparse(url)

    path_local = unicode(urllib.unquote(str(ps.path)), "utf-8")  # 从url转化为路径形式，具体为“urlencode -> utf-8 -> unicode”
    path_local = LOCAL_DIR + path_local
    logging.debug("sync dir %s, path = %s" % (url, path_local))

    if not os.path.exists(path_local):  # 若本地不存在该目录，则创建
        os.makedirs(path_local)

    html = urllib.urlopen(url)
    bs = BeautifulSoup(html, "html.parser")
    rows = bs.select("table tr")

    parse_row = partial(_parse_row, url=url, path_local=path_local)
    files = map(parse_row, rows[3:-1])  # 解析Tag， 返回FileStruct列表

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
    url = os.path.join(url, a.attrs["href"])  # 构造全完整url

    name = os.path.join(path_local, a.text)

    modify_time = next(children).text.strip()  # 去除字符串前后空格
    modify_time = int(mktime(strptime(modify_time, "%d-%b-%Y %H:%M")))  # 转换时间字符串为time整数, 原格式为“12-May-2016 18:45”

    # logging.debug("FileStruct : " + str((is_dir, url, name, modify_time),))
    return FileStruct(is_dir, url, name, modify_time)


def update(f):
    """根据给出的FileStruct判断是否需要更新本地的文件（夹），
    当文件（夹）不存在或者当前FileStruct代表的是文件夹亦或是文件的修改时间与FileStruct中修改时间不一致时返回True，即为需要修改"""
    return not os.path.exists(f.name) or os.path.isdir(f.name) or os.path.getmtime(f.name) != f.modify_time


@mte.async
def download(file_struct):
    urllib.urlretrieve(file_struct.url, file_struct.name)  # 下载文件
    os.utime(file_struct.name, (file_struct.modify_time, file_struct.modify_time))  # 设置文件的修改时间为网站上获取到的时间
    logging.debug("finished download %s from %s" % (file_struct.name, file_struct.url))

    record(file_struct)


update_files = []
record_lock = Lock()


def record(file_struct):
    with record_lock:
        insort(update_files, file_struct)


def display_file(files):
    for f in files:
        yield FileStruct(f.is_dir, os.path.dirname(f.url), f.name[len(LOCAL_DIR):],
                         strftime("%d-%b-%Y %H:%M", gmtime(f.modify_time)))


def dump_record(name):
    template = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html
        PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
        "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
    <title>Updates Cts Files</title>
</head>
<body>

<h1>Updates Cts Files</h1>

<table>
    <tr><th>File</th><th>Modify time</th></tr>
    {% for file in files %}
    <tr><td><a href='{{file.url}}'>{{file.name}}</a></td><td>{{file.modify_time}}</td></tr>
    {% endfor %}
</table>
</body>
</html>"""
    tp = Template(template)
    fn = os.path.join(LOCAL_LOG_DIR, 'updates-%s.html' % name)
    with open(fn, 'a+') as f:
        f.write(tp.render(files=display_file(update_files)).encode('utf-8'))


if __name__ == '__main__':
    start = time()

    cts_sync()
    mte.join()

    dump_record(strftime('%Y-%m-%d %H:%M:%S'))

    end = time()
    logging.debug("finish sync cts from server! Spent time : %f " % (end - start))
