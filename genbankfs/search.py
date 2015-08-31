import numexpr

import pandas as pd

from boltons.strutils import slugify

class GenbankSearch(object):
  def __init__(self, input_file):
    self.database = pd.read_csv(input_file, delimiter='\t')
    self.folders = ['species_taxid',
                    'taxid',
                    'organism_name',
                    'genus',
                    'species',
                    'accession']
    column_map = zip(['species_taxid',
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
    self.database['accession_slug'] = map(self._get_accession,
                                          self.database['ftp_path'])

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

  def _get_accession(self, ftp_path):
    return ftp_path.split('/')[-1]

  def build_url_lookup(self):
    accession_data = self.database[['accession_slug', 'ftp_path']]
    accession_map = dict(accession_data.values)
    def url_lookup(path):
      accession, filename = path.split('/')
      return "/".join([accession_map[accession], filename])
    return url_lookup
