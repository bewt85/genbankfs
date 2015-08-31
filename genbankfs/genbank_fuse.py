import logging
import os

from collections import namedtuple
from errno import ENOENT
from stat import S_IFDIR, S_IFLNK, S_IFREG
from sys import exit
from time import time

from fuse import FuseOSError, Operations, LoggingMixIn

if not hasattr(__builtins__, 'bytes'):
    bytes = str

class PathParseResult(namedtuple("PathParseResult", "file_path dir_name path_list query")):
  pass

class GenbankFuse(LoggingMixIn, Operations):
  def __init__(self, searcher, cache):
    self.searcher = searcher
    self.cache = cache
    self.parsers = {folder: self._parser_builder(folder)
                      for folder in self.searcher.folders}
    self.parsers['accession'] = self._parse_accession
    self.accession_files = [
      'README.txt',
      'md5checksums.txt',
      '{accession}_assembly_stats.txt',
      '{accession}_assembly_report.txt',
      '{accession}_genomic.fna.gz',
      '{accession}_genomic.gbff.gz',
      '{accession}_genomic.gff.gz'
    ]
    self.fn = 0
    super(GenbankFuse, self).__init__()

  def parse_path(self, path, query=None):
    query = {} if query == None else query

    drive_path, base_path = os.path.splitdrive(path)
    path_list = os.path.realpath(base_path).split(os.path.sep)
    assert path_list.pop(0) == '' # first element is ''

    def _parse_path(path_list, query):
      if len(path_list) == 0:
        return PathParseResult(None, 'default', [], query)

      parser = self.parsers.get(path_list[0], self._unparsable)
      result = parser(path_list, query)
      if len(result.path_list) == 0:
        return result
      else:
        return _parse_path(result.path_list, result.query)

    result = self._match_accession(path_list, query)
    if result.file_path:
      return result
    else:
      return _parse_path(path_list, query)

  def _unparsable(self, path_list, query):
    return PathParseResult(None, 'default', [], query)

  def _parser_builder(self, key):
    def parser(path_list, query):
      assert path_list[0] == key
      if len(path_list) == 1:
        return PathParseResult(None, key, [], query)
      elif len(path_list) > 1:
        query = dict(query)
        query[key] = path_list[1]
        return PathParseResult(None, 'default', path_list[2:], query)
      else:
        return PathParseResult(None, 'default', [], query)
    return parser

  def _parse_accession(self, path_list, query):
    assert path_list[0] == 'accession'
    if len(path_list) == 3:
      return self._match_accession(path_list, query)
    elif len(path_list) == 2:
      query = dict(query)
      query['accession'] = path_list[1]
      return PathParseResult(None, 'default', [], query)
    elif len(path_list) == 1:
      return PathParseResult(None, 'accession', [], query)
    else:
      return PathParseResult(None, 'default', [], query)

  def _match_accession(self, path_list, query):
    try:
      match_type, accession, filename = path_list[-3:]
      if match_type == 'accession':
        file_path = os.path.join(accession, filename)
        query = dict(query)
        query['accession'] = accession
        return PathParseResult(file_path, None, [], query)
    except ValueError:
      pass
    return PathParseResult(None, 'default', [], query)

  def readdir(self, path, fh):
    parse_result = self.parse_path(path)
    if parse_result.file_path:
      return [path]
    elif 'accession' in parse_result.query:
      accession_id = parse_result.query['accession']
      accession_files = [filename.format(accession=accession_id) for filename
                         in self.accession_files]
      return ['.', '..'] + accession_files
    elif parse_result.dir_name == 'default':
      folders = set(self.searcher.folders).difference(parse_result.query.keys())
      return ['.', '..'] + list(folders)
    else:
      return ['.', '..'] + self.searcher.list(parse_result.dir_name,
                                              **parse_result.query)

  def getattr(self, path, fh=None):
    parse_result = self.parse_path(path)
    if parse_result.file_path:
      return self.cache.getattr(parse_result.file_path)
    else:
      return dict(st_mode=(S_IFDIR | 0755), st_nlink=2,
                  st_size=0, st_ctime=time(), st_mtime=time(),
                  st_atime=time())

  def getxattr(self, path, name, position=0):
    return self.getattr(path).get(name, '')

  def listxattr(self, path):
    return self.getattr(path).keys()

  def open(self, path, flags):
    parse_result = self.parse_path(path)
    if parse_result.file_path:
      return self.cache.open(parse_result.file_path, flags)
    else:
      raise FuseOSError("Path '%s' was not parsable" % path)

  def read(self, path, size, offset, fh):
    return self.cache.read(size, offset, fh)

  def statfs(self, path):
    return dict(f_bsize=512, f_blocks=4096, f_bavail=2048)
