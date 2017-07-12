#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import os
import redis
import urllib
from collections import namedtuple
from functools import partial
from time import *
from urlparse import urlparse

from AsyncExecutor import async
from bs4 import BeautifulSoup

HOST = "http://172.26.35.223"
LOCAL_DIR = "/data/ubuntu16/ctsdemo"

FileStruct = namedtuple("FileStruct", ("is_dir", "url", "name", "modify_time"))

LOG_FORMAT = '%(asctime)s - %(filename)s[line:%(lineno)d] - %(threadName)s - %(levelname)s: %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

r = redis.Redis(host='127.0.0.1', port=6379)

REDIS_KEY_DIRS = 'cts_dirs'
REDIS_KEY_FILES = 'cts_files'
REDIS_KEY_UPDATES = 'cts_updates'


@async(15)
def sync_dir(url):
    ps = urlparse(url)

    path_local = unicode(urllib.unquote(str(ps.path)), "utf-8")  # 从url转化为路径形式，具体为“urlencode -> utf-8 -> unicode”
    path_local = LOCAL_DIR + path_local
    logging.info("sync dir %s, path = %s" % (url, path_local))

    if not os.path.exists(path_local):  # 若本地不存在该目录，则创建
        os.makedirs(path_local)

    try:
        html = urllib.urlopen(url)
    except Exception as e:
        # 访问量过大时出现IOERROR， “IOError: [Errno socket error] [Errno 104] Connection reset by peer”
        logging.exception(e)
        sync_dir(url)
        return

    r.sadd(REDIS_KEY_DIRS, path_local)  # 记录文件夹到数据库

    bs = BeautifulSoup(html, "html.parser")
    rows = bs.select("table tr")

    parse_row = partial(_parse_row, url=url, path_local=path_local)

    files = map(parse_row, rows[3:-1])  # 解析Tag， 返回FileStruct列表

    require_update = filter(update, files)  # 得到需要更新的文件（文件夹总是在返回结果中，因为还需要判断其中的文件是否有更新）
    logging.info("%s require_update %d:\n%s " % (path_local, len(require_update), pprint.pformat(require_update)))

    for f in require_update:
        if f.is_dir:
            sync_dir(f.url)
        else:
            download(f)


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

    return FileStruct(is_dir, url, name, modify_time)


def update(f):
    """根据给出的FileStruct判断是否需要更新本地的文件（夹），
    当文件（夹）不存在或者当前FileStruct代表的是文件夹亦或是文件的修改时间与FileStruct中修改时间不一致时返回True，即为需要修改"""
    if f.is_dir:
        return True

    changed = r.hget(REDIS_KEY_FILES, f.name) != str(f.modify_time)     # redis中取出的值总是字符串
    if changed:
        r.hset(REDIS_KEY_FILES, f.name, f.modify_time)
    return changed


@async(15)
def download(file_struct):
    # try:
    #     urllib.urlretrieve(file_struct.url, file_struct.name)  # 下载文件
    # except Exception as e:
    #     # 访问量过大时出现IOERROR， “IOError: [Errno socket error] [Errno 104] Connection reset by peer”
    #     logging.exception(e)
    #     download(file_struct)
    #     return

    logging.info("finished download %s from %s" % (file_struct.name, file_struct.url))
    # 去除本地路径前缀，保存更新过的文件到redis数据库
    r.sadd(REDIS_KEY_UPDATES, file_struct.name[len(LOCAL_DIR):])


if __name__ == '__main__':
    start = time()

    sync_dir(HOST + "/cts/")
    sync_dir.join()
    download.join()

    logging.info('dir count are %s' % r.scard(REDIS_KEY_DIRS))
    logging.info('file count are %s' % r.hlen(REDIS_KEY_FILES))
    logging.info('update count are %s' % r.scard(REDIS_KEY_UPDATES))
    end = time()
    logging.info("finish sync cts from server! Spent time : %f seconds" % (end - start))
