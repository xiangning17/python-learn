#!/usr/bin/env python
# -*- coding: utf-8 -*-
import functools
import logging
from Queue import PriorityQueue, Empty
from threading import Thread


class MultiThreadExecutor(object):
    def __init__(self, size=4):
        self.size = size
        self.task_queue = PriorityQueue()

        self.workers = None

        self.finish = False

    def loop(self):
        while not self.finish:
            try:
                priority, func, args, kw = self.task_queue.get(timeout=30)
                # logging.debug("invoke %s(%s, %s)" % (func.__name__, args, kw))
                func(*args, **kw)
            except Empty:
                continue
            finally:
                self.task_queue.task_done()
        logging.debug("worker thread finished!")

    def async(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            self.task_queue.put((1, func, args, kw))

        return wrapper

    def join(self):
        try:
            self.task_queue.join()
        finally:
            self.stop()

    def start(self):

        workers = []
        for i in range(self.size):
            t = Thread(target=self.loop, name="ThreadPool - %d" % i)
            t.setDaemon(True)
            t.start()
            workers.append(t)

        self.workers = workers

    def stop(self):
        self.finish = True
        logging.debug("stop workers...")

