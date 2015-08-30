import hashlib
import os
import shutil
import socket
import tempfile
import urllib

from urlparse import urlparse
from Queue import Queue, Full, Empty
from StringIO import StringIO
from threading import Lock, Thread, Event

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

  def retrieve_tempfile(self, url, temp_dir, *args, **kwargs):
    try:
      temp_file = tempfile.NamedTemporaryFile(mode='w',
                                              prefix=self._prefix_from_url(url),
                                              suffix='.tmp',
                                              dir=temp_dir,
                                              delete=True)
    except OSError:
      os.makedirs(temp_dir, 0755)
      temp_file = tempfile.NamedTemporaryFile(mode='w',
                                              prefix=self._prefix_from_url(url),
                                              suffix='.tmp',
                                              dir=temp_dir,
                                              delete=True)
    (filename, status) = self.retrieve(url, temp_file.name)
    return (temp_file, status)

  def _prefix_from_url(self, url):
    url_path = urlparse(url).path
    prefix = url_path.split('/')[-1]
    return prefix + '_'

def create_warning_file(root_dir, filename_prefix, message):
  message_digest = hashlib.md5(message).hexdigest()
  file_path = os.path.join(root_dir, 'tmp', "%s_%s.tmp" % (filename_prefix,
                                                           message_digest))
  if not os.path.isdir(os.path.join(root_dir, 'tmp')):
    os.makedirs(os.path.join(root_dir, 'tmp'), 0755)
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
    self.warning_files = {
      'queue': create_warning_file(self.root_dir, 'download_queue_warning',
                                   download_queue_warning.format(max_downloads=self.max_queue)),
      'timeout': create_warning_file(self.root_dir, 'download_timeout_warning', download_timeout_warning),
      'error': create_warning_file(self.root_dir, 'download_error', download_error)
    }
    self.download_locks = {}

  def open(self, path, flags):
    cache_path = os.path.join(self.root_dir, path)
    self._check_in_root(cache_path)
    try:
      return os.open(cache_path, flags)
    except OSError:
      pass
    try:
      origin_path = self.lookup(path)
    except:
      raise IOError('%s not found and not available for download') % path
    download_lock, download_complete_event = self.download_locks.setdefault(origin_path, (Lock(), Event()))
    if download_lock.acquire(False):
      download_fn = self.download(cache_path, origin_path, flags)
      download_complete_event.set()
      del self.download_locks[origin_path]
      download_lock.release()
    else:
      download_fn = self.wait_for_download(cache_path, flags, download_complete_event)
    return download_fn

  def read(self, size, offset, fh):
    with self.rwlock:
      os.lseek(fh, offset, 0)
      return os.read(fh, size)

  def wait_for_download(self, cache_path, flags, download_complete_event, timeout=600):
    download_complete_event.wait(timeout=timeout)
    try:
      return os.open(cache_path, flags)
    except OSError:
      return os.open(self.warning_files['timeout'], flags)

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
    download_staging_dir = os.path.join(self.root_dir, 'tmp')
    while True:
      cache_path, origin_path, flags, result = queue.get()

      # Double check it's not in the cache
      try:
        result.put(os.open(cache_path, flags))
      except OSError:
        pass # File doesn't exist so we should get started downloading it
      else:
        continue # Someone else downloaded it since this was queued

      # Download the file to a temporary location
      try:
        urllib.urlcleanup()
        download_tempfile, status = downloader.retrieve_tempfile(origin_path,
                                                                 download_staging_dir)
      except DownloadError:
        result.put(os.open(self.warning_files['error'], flags))
        queue.task_done()
        del download_tempfile
        continue

      # If the download was ok, move it where we need it
      try:
        shutil.move(download_tempfile.name, cache_path)
        result_fn = os.open(cache_path, flags)
      except IOError:
        intended_dir = os.path.dirname(os.path.realpath(cache_path))
        os.makedirs(intended_dir, mode=0755)
        shutil.move(download_tempfile.name, cache_path)
        result_fn = os.open(cache_path, flags)
      except:
        result_fn = os.open(self.warning_files['error'], flags)

      result.put(result_fn)
      queue.task_done()

      # Delete the tempfile (this should happen anyway)
      try:
        del download_tempfile
      except OSError:
        pass # If it was moved, this will fail but that's ok

  def _check_in_root(self, path):
    if not os.path.realpath(path).startswith(self.root_dir):
      raise IOError("Relative links in path would take us outside the root dir: %s not in %s" % (os.path.realpath(path), self.root_dir))
