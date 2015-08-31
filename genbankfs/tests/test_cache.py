#!/usr/bin/env python2

import os
import shutil
import tempfile
import time
import unittest

from Queue import Queue
from threading import Event, Thread

import genbankfs

from genbankfs import GenbankCache

def get_download_mock(download_trigger):
  class DownloadMock(object):
    def __init__(self, *args, **kwargs):
      self.temp_files = []
    def retrieve_tempfile(self, url, temp_dir, *args, **kwargs):
      download_trigger.wait()
      output_file = tempfile.NamedTemporaryFile(mode='w',
                                                prefix="fake_download_",
                                                suffix=".tmp",
                                                dir=temp_dir,
                                                delete=False)
      output_file.write("This is a fake file")
      output_file.close()
      self.temp_files.append(output_file)
      return output_file, None
  return DownloadMock

class TestParsePath(unittest.TestCase):
  def setUp(self):
    self.download_trigger = Event()
    self.original_DownloadWithExceptions = genbankfs.cache.DownloadWithExceptions
    genbankfs.cache.DownloadWithExceptions = get_download_mock(self.download_trigger)
    self.temp_dir = tempfile.mkdtemp(dir=os.getcwd(),
                                     prefix="cache_for_tests_",
                                     suffix="_tmp")
    self.cache = GenbankCache(self.temp_dir, lambda p: "www.fake.com" + p, 10)

  def queue_contents(self, path, queue):
    fh = self.cache.open(path, os.O_RDONLY)
    os.lseek(fh, 0, 0)
    contents = os.read(fh, 1000)
    queue.put(contents)
  
  def list_contents(self, queue):
    contents = []
    for i in xrange(queue.qsize()):
      contents.append(queue.get_nowait())
    return contents

  def test_open(self):
    self.download_trigger.set()
    fh = self.cache.open('foo', os.O_RDONLY)
    os.lseek(fh, 0, 0)
    actual = os.read(fh, 1000)
    expected = "This is a fake file"
    self.assertEqual(actual, expected)

  def test_open_10(self):
    queue = Queue()
    threads = [Thread(target=self.queue_contents, args=("foo_%s" % i, queue))
                for i in xrange(10)]
    for thread in threads:
      thread.start()
    contents = self.list_contents(queue)
    self.assertEqual(contents, [])
    time.sleep(0.1)
    self.assertEqual(self.cache.download_queue.qsize(), 8)
    self.download_trigger.set()
    for thread in threads:
      thread.join()
    contents = self.list_contents(queue)
    expected = ["This is a fake file"] * 10
    self.assertEqual(contents, expected)

  def test_open_12(self):
    queue = Queue()
    threads = [Thread(target=self.queue_contents, args=("foo_%s" % i, queue))
                for i in xrange(12)]
    for thread in threads:
      thread.start()
    contents = self.list_contents(queue)
    self.assertEqual(contents, [])
    time.sleep(0.1)
    self.assertEqual(self.cache.download_queue.qsize(), 10)
    self.download_trigger.set()
    for thread in threads:
      thread.join()
    contents = self.list_contents(queue)
    expected = ["This is a fake file"] * 12
    self.assertEqual(contents, expected)

  def test_open_13(self):
    queue = Queue()
    threads = [Thread(target=self.queue_contents, args=("foo_%s" % i, queue))
                for i in xrange(13)]
    for thread in threads:
      thread.start()
    time.sleep(0.1)
    contents = self.list_contents(queue)
    error_message = genbankfs.cache.download_queue_warning
    error_message = error_message % {'max_downloads': 10}
    self.assertEqual(contents, [error_message])
    self.assertEqual(self.cache.download_queue.qsize(), 10)
    self.download_trigger.set()
    for thread in threads:
      thread.join()
    contents = self.list_contents(queue)
    expected = ["This is a fake file"] * 12
    self.assertEqual(contents, expected)

  def test_open_1000(self):
    queue = Queue()
    threads = [Thread(target=self.queue_contents, args=("foo_%s" % i, queue))
                for i in xrange(1000)]
    for thread in threads:
      thread.start()
    time.sleep(0.1)
    contents = self.list_contents(queue)
    error_message = genbankfs.cache.download_queue_warning
    error_message = error_message % {'max_downloads': 10}
    self.assertEqual(contents, [error_message]*988)
    self.assertEqual(self.cache.download_queue.qsize(), 10)
    self.download_trigger.set()
    for thread in threads:
      thread.join()
    contents = self.list_contents(queue)
    expected = ["This is a fake file"] * 12
    self.assertEqual(contents, expected)

    # expect 12 downloads (10 queued, 2 from threads)
    # plus a directory for the tmp files
    cache_contents = os.listdir(self.temp_dir)
    self.assertEqual(len(cache_contents), 13)

    # expect the 12 downloaded files which the mock doesn't
    # delete itself plus the warning files
    download_dir = os.path.join(self.temp_dir, 'tmp')
    temp_files = os.listdir(download_dir)
    self.assertEqual(len(temp_files), 12 + len(self.cache.warning_files))

  def tearDown(self):
    self.download_trigger.set()
    #shutil.rmtree(self.temp_dir)
    genbankfs.cache.DownloadWithExceptions = self.original_DownloadWithExceptions

if __name__ == '__main__':
  unittest.main()
