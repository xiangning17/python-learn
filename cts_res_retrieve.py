#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3
import urllib
from urlparse import urlparse

from apscheduler.schedulers.blocking import BlockingScheduler
from bs4 import BeautifulSoup
import os
from shutil import rmtree
from datetime import datetime
from Queue import Queue, Empty
import threading
import logging

LOG_FORMAT = '%(asctime)s - %(filename)s[line:%(lineno)d] - %(threadName)s - %(levelname)s: %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
file_handler = None


HOST = "http://172.26.35.223"
LOCAL_DIR = "/data/ubuntu16/ctsdemo"
WORKER_THREAD_SIZE = 30

finished = False
retrieve_count = 0
lock = threading.Lock()
db = threading.local()
db_lock = threading.Lock()
task_queue = Queue()


def retrieve_cts():

    global finished, retrieve_count
    finished = False
    retrieve_count = 0

    start_worker()  # start worker thread.
    start_time = datetime.now()
    retrieve("/cts/")   # add the '/cts/' to queue.
    try:
        task_queue.join()   # waiting for queue empty.
    finally:
        finished = True  # mark finished.
    end_time = datetime.now()
    logging.info("finish retrieve with time : %s" % (end_time - start_time))
    logging.info("finish retrieve with retrieve_count : %d" % retrieve_count)


def start_worker():
    for i in range(WORKER_THREAD_SIZE):
        t = threading.Thread(target=_loop, name="worker-" + str(i))
        t.setDaemon(True)
        t.start()


def _loop():
    db.cursor = open_db()   # get a db connection for every thread.
    global retrieve_count
    while not (finished and task_queue.empty()):
        # logging.info("get %d url from queue..." % retrieve_count)
        try:
            task = task_queue.get(timeout=30)
        except Empty:
            logging.error("get task from queue timeout...")
            continue

        if isinstance(task, tuple):     # download the file.
            file_url, file_name = task
            try:
                urllib.urlretrieve(file_url, file_name)
                logging.info("download file %s from %s finished" % (file_name, file_url))
            except Exception, e:
                logging.exception(e)
                task_queue.put(task)
        elif isinstance(task, str) or isinstance(task, unicode):    # retrieve the directory.
            url = task
            logging.info("start retrieve url : " + url)
            try:
                _do_retrieve(url)
                logging.info("finish retrieve url : " + url)
            except Exception, e:
                logging.exception(e)
                retrieve(url)
                logging.error("retry retrieve url : " + url)
        task_queue.task_done()  # aways mark task done to avoid the 'task_queue.join()' suspend.

    db.cursor.connection.close()
    logging.info("finish worker!")


def retrieve(relative_url):
    """retrieve the relative_url, but this just put it into queue and waiting for process."""

    global retrieve_count

    # max_retrieve_directory = 2000
    # if retrieve_count >= max_retrieve_directory:  # for debug, just retrieve 2000 directory urls.
    #     global finished
    #     finished = True
    #     logging.info("retrieve %d directory, mark finished!" % max_retrieve_directory)
    #     return

    lock.acquire()
    retrieve_count += 1
    lock.release()

    task_queue.put(relative_url)    # put the request url to queue.


def _do_retrieve(directory_url):
    """the real operation for retrieve the directory

    relative_url : the url relative web root"""

    directory_name = LOCAL_DIR + unicode(urllib.unquote(str(directory_url)), "utf-8")
    directory_url = HOST + directory_url
    html = urllib.urlopen(directory_url)
    if html.code != 200:
        logging.info("visit %s error!" % directory_url)
        return

    if not os.path.exists(directory_name):
        os.makedirs(directory_name)
        logging.info("mkdirs : " + directory_name)

    list_files = os.listdir(directory_name)

    bs = BeautifulSoup(html, "html.parser")
    rows = bs.select("table tr")
    for tag in rows[3:-1]:
        is_dir, url, name, mod_date = _process_row(tag)

        for f in list_files:    # count the diff between server and local.
            if f == name:
                list_files.remove(f)

        full_url = directory_url + url
        full_name = directory_name + name

        if is_dir:
            retrieve(urlparse(full_url).path)   # just use the url path as params.
        elif _update_date(full_name[len(LOCAL_DIR):], mod_date) or not os.path.exists(full_name):
            # urllib.urlretrieve(full_url, full_name)
            task_queue.put((full_url, full_name))   # put it to task queue.

    for f in list_files:   # the left file in list_files present someone be deleted from server.
        f = directory_name + f
        if os.path.isdir(f):
            rmtree(f)
        else:
            os.remove(f)
        logging.info("server delete " + f)


def _process_row(tag):
    """process a row and return four value:

    is_dir -> indicate whether the row present a directory.

    url -> the relative url of current file/dir

    name -> the display name of current file/dir

    modify_date -> the modify date of current file/dir"""

    is_dir = False

    children = tag.children

    img = next(children).img
    if img.attrs["alt"] == "[DIR]":
        is_dir = True

    a = next(children).a
    url = a.attrs["href"]
    name = a.text[:-1] if is_dir else a.text   # for dir like "cts/", remove the last "/"

    modify_date = next(children).text

    return is_dir, url, name, modify_date


def open_db():
    con = sqlite3.connect("./cts_res_retrieve.db")
    con.execute(
        "CREATE TABLE IF NOT EXISTS modify_time ("
        "filename TEXT PRIMARY KEY ,"
        "datetext TEXT NULL)"
    )
    con.commit()
    return con.cursor()


def _update_date(path, newdate):
    """compare the newdate with date in db, then return True if db has been updated otherwise False

    path -> the file path as the key

    newdate -> the new modify date of this file/dir"""

    saved_date = _get_date(path)

    if saved_date == newdate:
        logging.info("%s not changed!" % path)
        return False

    if saved_date is None:
        statement = "INSERT INTO modify_time (datetext,filename) VALUES (?,?)"
    else:
        statement = "UPDATE modify_time SET datetext=? WHERE filename=?"
    logging.info("execute : " + statement.replace("?", "%s") % (newdate, path))

    with db_lock:
        db.cursor.execute(statement, (newdate, path))
        db.cursor.connection.commit()

    return True


def _get_date(path):
    statement = "SELECT datetext FROM modify_time WHERE filename=?"
    # while not db_read_event.isSet():
    #     db_read_event.wait()
    with db_lock:
        db.cursor.execute(statement, (path,))
        result = db.cursor.fetchone()
    return result[0] if result else None


def get_file_logging_handler(filename):
    fh = logging.FileHandler(filename)
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    return fh


if __name__ == '__main__':

    scheduler = BlockingScheduler(daemonic=False)

    @scheduler.scheduled_job('cron', day='*', hour='18', minute='0')
    def main():
        global file_handler
        logger = logging.getLogger()
        logger.removeHandler(file_handler)
        file_handler = get_file_logging_handler(str(datetime.now()) + ".log")
        logger.addHandler(file_handler)

        retrieve_cts()
        file_handler.flush()
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logging.info("retrieve cts task has been shutdown!")