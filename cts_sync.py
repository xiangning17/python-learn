#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import os
import redis
import urllib
from collections import namedtuple
from time import *
from urlparse import urlparse

import re
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED
import shutil

from AsyncExecutor import async
from bs4 import BeautifulSoup

HOST = "http://172.26.35.223"
LOCAL_DIR = "/data/ubuntu16/ctsdemo"

FileStruct = namedtuple("FileStruct", ("is_dir", "url", "name", "modify_time"))
Result = namedtuple('Result', ('name', 'projet', 'version', 'perso', 'type', 'time'))

LOG_FORMAT = '%(asctime)s - %(filename)s[line:%(lineno)d] - %(threadName)s - %(levelname)s: %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

r = redis.Redis(host='127.0.0.1', port=6379)

REDIS_KEY_DIRS = 'cts_dirs'
REDIS_KEY_FILES = 'cts_files'
REDIS_KEY_UPDATES = 'cts_updates'


@async(15)
def sync_dir(url):
    ps = urlparse(url)

    path = unicode(urllib.unquote(str(ps.path)), "utf-8")  # 从url转化为路径形式，具体为“urlencode -> utf-8 -> unicode”
    logging.info("sync dir %s, path = %s" % (url, path))

    try:
        html = urllib.urlopen(url)
    except Exception as e:
        # 访问量过大时出现IOERROR， “IOError: [Errno socket error] [Errno 104] Connection reset by peer”
        logging.exception(e)
        sync_dir(url)
        return

    r.sadd(REDIS_KEY_DIRS, path)  # 记录文件夹到数据库

    bs = BeautifulSoup(html, "html.parser")
    rows = bs.select("table tr")

    files = (_parse_row(row, url, path) for row in rows[3:-1])    # 解析Tag， 返回FileStruct列表

    require_update = filter(update, files)  # 得到需要更新的文件（文件夹总是在返回结果中，因为还需要判断其中的文件是否有更新）

    for f in require_update:
        if f.is_dir:
            sync_dir(f.url)
        else:
            logging.info("update files %s" % f.name)    # 保存更新过的文件到redis数据库
            r.sadd(REDIS_KEY_UPDATES, f.name)


def _parse_row(tag, url, parent_dir):
    """解析一行代表文件/文件夹的“td”标签"""
    is_dir = False

    children = tag.children

    img = next(children).img
    if img.attrs["alt"] == "[DIR]":
        is_dir = True

    a = next(children).a
    url = os.path.join(url, a.attrs["href"])  # 构造全完整url

    name = os.path.join(parent_dir, a.text)

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


@async(10)
def make_zip(resulut):
    tmp_dir = tempfile.mkdtemp()    # 创建临时目录
    result_zip = os.path.join(tmp_dir, resulut.time + '.zip')      # 打包的zip文件名（置于临时目录下）
    with ZipFile(result_zip, 'w', ZIP_DEFLATED) as zf:
        dir_name = os.path.dirname(resulut.name)     # 得到result.xml的父目录，在该目录下的所有东西需要放入zip中

        for fn, _ in r.hscan_iter(REDIS_KEY_FILES, dir_name + '/*'):
            base_name = os.path.join(resulut.time, fn[len(dir_name) + 1:])    # 以时间作为前缀路径， +1 是加上父目录后路径分隔符‘/’的长度
            url = HOST + fn        # 拼接url
            tmp_path = os.path.join(tmp_dir, 'tmp')  # 在临时目录创建一个临时文件用于暂存下载下来的文件
            urllib.urlretrieve(url, tmp_path)
            zf.write(tmp_path, base_name)            # 将下载下来的临时文件以其base_name打包进zip文件

    # do operation of result and zip.

    logging.info('remove tmp dir: %s' % tmp_dir)
    shutil.rmtree(tmp_dir)         # 删除临时目录以及其下所有内容


def process_cts_gts_updates():
    p = re.compile(r'/cts/([A-Z].+)/(\w+)/(\w+)/((cts_Result)|(gts_Result))/(.+[Rr]esult.xml)')

    updates = []
    for f in r.sscan_iter(REDIS_KEY_UPDATES):
        m = p.match(f)
        if m:
            name = f
            pro = m.group(1)
            ver = m.group(2)
            per = m.group(3)
            t = 'cts' if m.group(5) else 'gts'

            modify_time = r.hget(REDIS_KEY_FILES, f)
            tm = strftime("%Y.%m.%d_%H.%M.%S", localtime(float(modify_time)))

            updates.append(Result(name, pro, ver, per, t, tm))

    for up in updates:
        logging.info('process result: %s' % str(up))
        make_zip(up)


if __name__ == '__main__':
    start = time()
    r.delete(REDIS_KEY_UPDATES)     # 先删除之前的updates记录
    sync_dir(HOST + "/cts/")
    sync_dir.join()

    logging.info('dir count are %s' % r.scard(REDIS_KEY_DIRS))
    logging.info('file count are %s' % r.hlen(REDIS_KEY_FILES))
    logging.info('update count are %s' % r.scard(REDIS_KEY_UPDATES))
    end = time()
    logging.info("finish sync cts from server! Spent time : %f seconds" % (end - start))
    process_cts_gts_updates()
    make_zip.join()
