#!/usr/bin/env python
# -*- coding: utf-8 -*-
import functools
from multiprocessing import cpu_count
from time import sleep

from concurrent.futures import thread


class MultiThreadExecutor(object):
    def __init__(self, size=cpu_count() * 2):
        self._pool = thread.ThreadPoolExecutor(size)

    def async(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            self._pool.submit(func, *args, **kw)

        return wrapper

    def join(self):

        sleep(3)    # 先等待3s以让初始任务触发更多任务

        task_queue = self._pool._work_queue

        while not task_queue.empty():
            sleep(1)

        self._pool.shutdown()
