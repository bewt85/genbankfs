import hashlib
import os
import socket
import urllib

from Queue import Queue, Full, Empty
from StringIO import StringIO
from threading import Lock, Thread

# Set download timeout
socket.setdefaulttimeout(600)

class DownloadError(Exception):
  pass

class DownloadWithExceptions(urllib.FancyURLopener):
  def error(self, *args, **kwargs):
    raise DownloadError("There was a problem with your download")
  http_error_401 = error
  http_error_403 = error
  http_error_404 = error

def create_warning_file(root_dir, filename_prefix, message):
  message_digest = hashlib.md5(message).hexdigest()
  file_path = os.path.join(root_dir, 'tmp', "%s_%s.tmp" % (filename_prefix,
                                                           message_digest))
  if not os.path.isdir(os.path.join(root_dir, 'tmp')):
    os.mkdir(os.path.join(root_dir, 'tmp'), 0755)
  if not os.path.isfile(file_path):
    with open(file_path, 'w') as f:
      f.write(message)
  return os.path.abspath(file_path)

download_queue_warning = """\
WARNING: You seem to be downloading a lot!

To protect you from accidentally downloading all of
the internet at once, we've implemented a queue
system which means that you can only request up to
%(max_downloads)s downloads at once.  If you ask
for more than this, the first %(max_downloads)s
are downloaded and this message is temporarily
returned.

To get the files you want, simply wait a few
minutes and retry by which time you should be able
to get a few more of them.

Apologies for the inconvenience
"""

download_timeout_warning = """\
WARNING: The download timed out

We couldn't find this file in our cache so tried
to download it.  Unfortunately the download timed
out.  Please try again later
"""

download_error = """\
WARNING: There was a problem downloading this file

Please try again later
"""

class GenbankCache(object):
  def __init__(self, root_dir, lookup_func, max_queue=100, concurent_downloads=2):
    self.lookup = lookup_func
    self.max_queue = max_queue
    self.root_dir = os.path.realpath(root_dir)
    self.download_queue = Queue(maxsize=max_queue)
    self.rwlock = Lock()
    self.threads = [Thread(target=self._download_queued, args=(self.download_queue,))
                      for i in xrange(concurent_downloads)]
    for thread in self.threads:
      thread.daemon = True
      thread.start()
    # TODO: create root dir if missing
    self.warning_files = {
      'queue': create_warning_file(self.root_dir, 'download_queue_warning',
                                   download_queue_warning.format(max_downloads=self.max_queue)),
      'timeout': create_warning_file(self.root_dir, 'download_timeout_warning', download_timeout_warning),
      'error': create_warning_file(self.root_dir, 'download_error', download_error)
    }

  def open(self, path, flags):
    cache_path = os.path.join(self.root_dir, path)
    self._check_in_root(cache_path)
    # TODO: what if path includes a directory which doesn't exist?
    try:
      return os.open(cache_path, flags)
    except OSError:
      pass
    try:
      origin_path = self.lookup(path)
    except:
      raise IOError('%s not found and not available for download') % path
    return self.download(cache_path, origin_path, flags)

  def read(self, size, offset, fh):
    with self.rwlock:
      os.lseek(fh, offset, 0)
      return os.read(fh, size)

  def download(self, cache_path, origin_path, flags, timeout=600):
    result = Queue()
    try:
      self.download_queue.put_nowait((cache_path, origin_path, flags, result))
      output_file = result.get(timeout=timeout)
      return output_file
    except Full:
      return os.open(self.warning_files['queue'], flags)
    except Empty:
      return os.open(self.warning_files['timeout'], flags)

  def _download_queued(self, queue):
    downloader = DownloadWithExceptions()
    while True:
      cache_path, origin_path, flags, result = queue.get()
      try:
        # TODO: what if it was downloaded since it was originally queued?
        # TODO: what if the target directory doesn't exist?
        download_path, status = downloader.retrieve(origin_path, cache_path)
        result.put(os.open(download_path, flags))
      except:
        result.put(os.open(self.warning_files['error'], flags))
      finally:
        queue.task_done()

  def _check_in_root(self, path):
    if not os.path.realpath(path).startswith(self.root_dir):
      raise IOError("Relative links in path would take us outside the root dir: %s not in %s" % (os.path.realpath(path), self.root_dir))
