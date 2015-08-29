#!/usr/bin/env python

import argparse
import numexpr

import pandas as pd

from errno import ENOENT
from stat import S_IFDIR, S_IFLNK, S_IFREG
from sys import exit
from time import time
from boltons.strutils import slugify

from fuse import FUSE, FuseOSError, Operations

if not hasattr(__builtins__, 'bytes'):
    bytes = str

class GenbankSearch(object):
  def __init__(self, input_file):
    self.database = pd.read_csv(input_file, delimiter='\t')
    self.folders = ['accession',
                    'species_taxid',
                    'taxid',
                    'organism_name',
                    'genus',
                    'species']
    column_map = zip(['# assembly_accession',
                       'species_taxid',
                       'taxid',
                       'organism_name'],
                       self.folders)
    for original_column, slug_column in column_map:
      self.database[slug_column+'_slug'] = map(self._slug,
                                               self.database[original_column])
    self.database['genus_slug'] = map(self._get_genus,
                                        self.database['organism_name'])
    self.database['species_slug'] = map(self._get_species,
                                        self.database['organism_name'])

  def query(self, **terms):
    relevant_terms = {key+'_slug': self._slug(value)
                        for key,value in terms.items()
                        if key in self.folders}
    query_str = " & ".join(["{} == '{}'".format(key, value) for key,value in
                       relevant_terms.items()])
    if not query_str:
      return self.database
    return self.database.query(query_str)

  def list(self, folder, **terms):
    if not folder in self.folders:
      raise ValueError("{} not in folders".format(folder))
    return list(set(self.query(**terms)[folder+'_slug']))

  def _slug(self, value):
    return slugify(str(value), lower=True)

  def _get_genus(self, species_name):
    genus, species = species_name.split(" ", 2)[:2]
    return self._slug(genus)

  def _get_species(self, species_name):
    genus, species = species_name.split(" ", 2)[:2]
    return self._slug("%s_%s" % (genus, species))

class GenbankCache(object):
  pass

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

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("assembly_details", type=argparse.FileType('r'))
  parser.add_argument("mount_point", type=str)
  args = parser.parse_args()

  searcher = GenbankSearch(args.assembly_details)
  fuse = FUSE(GenbankFuse(searcher), args.mount_point, foreground=True)
