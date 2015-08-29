from setuptools import setup

import genbankfs

setup(
  name='genbankfs',
  version=genbankfs.__version__,
  licence='GPL v3',
  install_requires=[
    'boltons>=15.0.0',
    'fusepy>=2.0.2',
    'numexpr>=2.4.3',
    'numpy>=1.9.2',
    'pandas>=0.16.2'
  ],
  packages=['genbankfs'],
  scripts=['scripts/genbankfs-start']
)
