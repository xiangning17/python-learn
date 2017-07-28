#!/usr/bin/env python
# -*- coding: utf-8 -*-
import functools
import logging
from multiprocessing import cpu_count
from threading import Condition
from time import sleep

from concurrent.futures import ThreadPoolExecutor


class AsyncExecutor(object):
    """
    多线程异步执行器，提供join方法等待所有任务完成然后关闭执行器。
    还可以添加异常处理器。
    """

    def __init__(self, size=cpu_count()*2, name='default', exception_handler=None):

        self._pool = ThreadPoolExecutor(size)

        self._count = 0

        self._condition = Condition()

        self._name = '[Pool-%s] : ' % name

        self._exception_handler = exception_handler

    def _exception_catcher(self, f, *args, **kwargs):
        r = None
        try:
            r = f(*args, **kwargs)
        except Exception as e:
            logging.exception('AsyncExecutor Caught exception. %s' % e.message)
            if self._exception_handler:
                self._exception_handler(e, f, *args, **kwargs)

        return r

    def _done_callback(self, future):
        logging.debug(self._name + 'done_callback for %s!' % future)
        if future.exception():
            logging.exception(future.exception().message)

        with self._condition:
            self._count -= 1
            if self._count < 1:
                logging.info(self._name + 'done_callback notify all task finished!')
                self._condition.notifyAll()

    def join(self, time=None):
        if time:
            logging.info(self._name + 'waiting for join and sleep %s seconds...' % time)
            sleep(time)
        with self._condition:
            while self._count > 0:
                logging.info(self._name + 'wating for task finish...')
                self._condition.wait()

        logging.info(self._name + 'there are no more task, shutdown pool...')
        self._pool.shutdown()

    def submit(self, fn, *args, **kw):
        future = self._pool.submit(self._exception_catcher, fn, *args, **kw)
        future.add_done_callback(self._done_callback)
        logging.debug(self._name + 'submit for %s!' % future)
        with self._condition:
            self._count += 1
        return future


def async(n, exception_handler=None):

    def decoration(func):

        name = func.__name__ if hasattr(func, '__name__') else 'default'
        executor = AsyncExecutor(n, name, exception_handler)

        @functools.wraps(func)
        def wrapper(*args, **kw):
            return executor.submit(func, *args, **kw)

        wrapper.join = func.join = lambda t=3: executor.join(t)
        return wrapper

    return decoration



