#!/usr/bin/env python2

import unittest

from mock import patch, MagicMock

from genbankfs import GenbankFuse
from genbankfs.genbank_fuse import PathParseResult

def fake_path_join(*args):
  return '/'.join(args)

class TestParsePath(unittest.TestCase):
  def setUp(self):
    searcher = MagicMock()
    cache = MagicMock()
    searcher.folders = ['species_taxid',
                    'taxid',
                    'organism_name',
                    'genus',
                    'species',
                    'accession']
    self.fuse = GenbankFuse(searcher, cache)

  @patch('genbankfs.genbank_fuse.os.path.join')
  def test_match_accession_happy(self, join_mock):
    join_mock.side_effect = fake_path_join
    path_list = '/accession/foo/bar.txt'.split('/')
    result = self.fuse._match_accession(path_list, {})
    self.assertEqual(result.file_path, 'foo/bar.txt')
    self.assertEqual(result.dir_name, None)
    self.assertEqual(result.path_list, [])
    self.assertEqual(result.query, {'accession': 'foo'})

  @patch('genbankfs.genbank_fuse.os.path.join')
  def test_match_accession_unhappy(self, join_mock):
    join_mock.side_effect = fake_path_join
    path_list = '/foo/bar/baz.txt'.split('/')
    result = self.fuse._match_accession(path_list, {})
    self.assertEqual(result.file_path, None)
    self.assertEqual(result.dir_name, 'default')
    self.assertEqual(result.path_list, [])
    self.assertEqual(result.query, {})

    path_list = '/bar.txt'.split('/')
    result = self.fuse._match_accession(path_list, {})
    self.assertEqual(result.file_path, None)
    self.assertEqual(result.dir_name, 'default')
    self.assertEqual(result.path_list, [])
    self.assertEqual(result.query, {})

  def test_parser_builder(self):
    parser = self.fuse._parser_builder('foo')
    self.assertRaises(AssertionError, parser, ['bar'], {})
    
    expected = PathParseResult(None, 'foo', [], {})
    self.assertEqual(parser(['foo'], {}), expected)

    expected = PathParseResult(None, 'default', [], {'foo': 'bar'})
    self.assertEqual(parser(['foo', 'bar'], {}), expected)

    expected = PathParseResult(None, 'default', [], {'foo': 'bar', 'baz': 1})
    self.assertEqual(parser(['foo', 'bar'], {'foo': 'quux', 'baz': 1}), expected)

    expected = PathParseResult(None, 'default', ['baz'], {'foo': 'bar'})
    self.assertEqual(parser(['foo', 'bar', 'baz'], {}), expected)

  def test_parse_path_single(self):
    path = '/accession'
    result = self.fuse.parse_path(path, {})
    expected = PathParseResult(None, 'accession', [], {})
    self.assertEqual(result, expected)

    path = '/taxid'
    result = self.fuse.parse_path(path, {})
    expected = PathParseResult(None, 'taxid', [], {})
    self.assertEqual(result, expected)

    path = '/species'
    result = self.fuse.parse_path(path, {})
    expected = PathParseResult(None, 'species', [], {})
    self.assertEqual(result, expected)

    path = '/genus'
    result = self.fuse.parse_path(path, {})
    expected = PathParseResult(None, 'genus', [], {})
    self.assertEqual(result, expected)

    path = '/foo'
    result = self.fuse.parse_path(path, {})
    expected = PathParseResult(None, 'default', [], {})
    self.assertEqual(result, expected)

  def test_parse_multi(self):
    path = '/genus/foo'
    result = self.fuse.parse_path(path, {})
    expected = PathParseResult(None, 'default', [], {"genus": "foo"})
    self.assertEqual(result, expected)

    path = '/genus/foo/taxid'
    result = self.fuse.parse_path(path, {})
    expected = PathParseResult(None, 'taxid', [], {"genus": "foo"})
    self.assertEqual(result, expected)

    path = '/genus/foo/taxid/1000'
    result = self.fuse.parse_path(path, {})
    expected = PathParseResult(None, 'default', [], {"genus": "foo", "taxid": "1000"})
    self.assertEqual(result, expected)

    path = '/genus/foo/taxid/1000/accession/ABC'
    result = self.fuse.parse_path(path, {})
    expected_query = {
      "genus": "foo", 
      "taxid": "1000",
      'accession': 'ABC'
    }
    expected = PathParseResult(None, 'default', [], expected_query)
    self.assertEqual(result, expected)

    path = '/genus/foo/taxid/1000/accession/ABC/README.txt'
    result = self.fuse.parse_path(path, {})
    expected_query = {
      'accession': 'ABC'
    }
    expected = PathParseResult('ABC/README.txt', None, [], expected_query)
    self.assertEqual(result, expected)

  def test_parse_nonsense(self):
    path = '/genus/foo/taxid/NONSENSE/1000/accession/ABC'
    result = self.fuse.parse_path(path, {})
    expected_query = {
      "genus": "foo", 
      "taxid": "NONSENSE",
    }
    expected = PathParseResult(None, 'default', [], expected_query)
    self.assertEqual(result, expected)

    path = '/genus/foo/taxid/1000/NONSENSE/accession/ABC'
    result = self.fuse.parse_path(path, {})
    expected_query = {
      "genus": "foo", 
      "taxid": "1000",
    }
    expected = PathParseResult(None, 'default', [], expected_query)
    self.assertEqual(result, expected)

    path = '/genus/foo/taxid/1000/NONSENSE/accession/ABC/README.txt'
    result = self.fuse.parse_path(path, {})
    expected_query = {
      'accession': 'ABC'
    }
    expected = PathParseResult('ABC/README.txt', None, [], expected_query)
    self.assertEqual(result, expected)

if __name__ == '__main__':
  unittest.main()
