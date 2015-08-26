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
  def __init__(self, csv_filename):
    self.columns = dict(zip(['# assembly_accession',
                             'taxid',
                             'organism_name'],
                            ['accession',
                             'taxid',
                             'organism_name']
                           ))
    self.database = pd.read_csv(csv_filename, delimiter='\t')
    for original_column, slug_column in self.columns.items():
      self.database[slug_column+'_slug'] = map(self._slug, self.database[original_column])

  def query(self, **terms):
    relevant_terms = {key+'_slug': self._slug(value)
                        for key,value in terms.items()
                        if key in self.columns.values()}
    query_str = " & ".join(["{} == '{}'".format(key, value) for key,value in
                       relevant_terms.items()])
    if not query_str:
      return self.database
    return self.database.query(query_str)

  def list(self, column, **terms):
    if not column in self.columns.values():
      raise ValueError("{} not in columns".format(column))
    return list(set(self.query(**terms)[column+'_slug']))

  def _slug(self, value):
    return slugify(str(value), lower=False)

class GenbankCache(object):
  pass

class GenbankFuse(Operations):
  pass

if __name__ == '__main__':
  pass
