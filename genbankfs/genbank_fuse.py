from errno import ENOENT
from stat import S_IFDIR, S_IFLNK, S_IFREG
from sys import exit
from time import time

from fuse import FuseOSError, Operations

if not hasattr(__builtins__, 'bytes'):
    bytes = str

class GenbankFuse(Operations):
  def __init__(self, searcher):
    self.searcher = searcher
    super(GenbankFuse, self).__init__()

  def readdir(self, path, fh):
    print path
    if path == '/accession':
      return ['.', '..'] + self.searcher.list('accession')
    return ['.', '..', 'genus', 'taxid', 'species_taxid', 'accession']

  def getattr(self, path, fh=None):
    return dict(st_mode=(S_IFDIR | 365), st_nlink=2,
                st_size=0, st_ctime=time(), st_mtime=time(),
                st_atime=time())
