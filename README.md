# Genbankfs

Genbank is a FUSE based filesystem which lets you navigate Bacteria in
Genbank as if you'd already downloaded them onto your laptop / server.

Folders can be navigated by:
- accession
- genus
- organism_name
- species
- species_taxid
- taxid

Files are only (meant to be) downloaded when you actually read them.
Downloads are queued and (by default) only downloaded two at a time.
The queue is also limited to try and avoid you accidentally
requesting all of Genbank without noticing.

Downloads are cached in a specified folder (defaulting to a folder
in your home directory).  Next time you try and open a file it should
open straight away.

By default some errors (like trying to download too much) will result
in fake file contents with a suitable warning.

Lots of inspiration for the FUSE elements is drawn from [the examples
in fusepy](https://github.com/terencehonles/fusepy/tree/master/examples).

## Warning!
This project is not endorsed by NCBI or my employer. I've tried to stop
it from filling up your hard disk / doing other bad things but it still
might.  You probably shouldn't use it.

## Installation

```
pip install git+https://github.com/bewt85/genbankfs.git
```

## Usage

You need some metadata in tab separated format; the NCBI hosts such a
file for [bacteria genomes here](ftp://ftp.ncbi.nlm.nih.gov/genomes/genbank/bacteria/assembly_summary.txt).

You can also make your own.  The format for this is at the end of this
README.

```
mkdir genbank
wget ftp://ftp.ncbi.nlm.nih.gov/genomes/genbank/bacteria/assembly_summary.txt
genbankfs-start --cache tmp_cache assembly_summary.txt genbank
```

In another terminal, you can now do the following:
```
me@~/Projects/genbankfs$ cd genbank
me@genbank$ ls
accession	organism_name	species_taxid
genus		species		taxid
me@genbank$ cd genus/streptococcus/
me@genbank/genus/streptococcus$ ls
accession	organism_name	species		species_taxid	taxid
me@genbank/genus/streptococcus$ cd organism_name/*_r6
me@genbank/genus/streptococcus/organism_name/streptococcus_pneumoniae_r6$ ls
accession	species		species_taxid	taxid
me@genbank/genus/streptococcus/organism_name/streptococcus_pneumoniae_r6$ cd accession/
me@genbank/genus/streptococcus/organism_name/streptococcus_pneumoniae_r6/accession$ ls
GCA_000007045.1_ASM704v1
me@genbank/genus/streptococcus/organism_name/streptococcus_pneumoniae_r6/accession/GCA_000007045.1_ASM704v1$ ls
GCA_000007045.1_ASM704v1_assembly_report.txt
GCA_000007045.1_ASM704v1_assembly_stats.txt
GCA_000007045.1_ASM704v1_genomic.fna.gz
GCA_000007045.1_ASM704v1_genomic.gbff.gz
GCA_000007045.1_ASM704v1_genomic.gff.gz
README.txt
md5checksums.txt
me@~/Projects/genbankfs/genbank/genus/streptococcus/organism_name/streptococcus_pneumoniae_r6/accession/GCA_000007045.1_ASM704v1$ gunzip -c GCA_000007045.1_ASM704v1_genomic.gbff.gz | head
LOCUS       AE007317             2038615 bp    DNA     circular BCT 30-JAN-2014
DEFINITION  Streptococcus pneumoniae R6, complete genome.
ACCESSION   AE007317 AE008385-AE008568
VERSION     AE007317.1  GI:25307955
DBLINK      BioProject: PRJNA278
            BioSample: SAMN02603218
KEYWORDS    .
SOURCE      Streptococcus pneumoniae R6
  ORGANISM  Streptococcus pneumoniae R6
            Bacteria; Firmicutes; Bacilli; Lactobacillales; Streptococcaceae;
```

## Known issues

The most annoying are that you have to lie to your shell about the size
of files.  It takes a few seconds to get the actual sizes of each file
and I didn't want to have to download them all in advance or wait for
them while navigating around folders.  I originally just said that
uncached files have a size of 0 bytes, but some tools like `cat`
refused to do anything with this.  I've now changed to saying that
unknown files are all approximately 1TB which seems to result in
better behaviour from most tools.

The other issue is that many tools (e.g. `head`) don't like waiting
for ages to get bytes when they read a file and create a 'Socket' error.
I could get round this by downloading bits of each file in the queue and
returning them slowly to keep consuming services sweet, but this is
likely to add loads of complication for not a lot of benefit.

## Conclusions

This tool was interesting to write and taught me a lot about file
systems and threaded python which I didn't know.  It's kind of useful
if you know roughly what data you want and you just want to download
a couple of files but it's not really revolutionary.

The tool I actually probably need would need access to more metadata
about what is in the files (e.g. N50, number of contigs, mapping data?)
but a filesystem interface to that is likely to be pretty unworkable.

I'm therefore not going to continue with development but this will
hopefully be a useful reference to me (and others) in the future.

## Metadata format

You probably want to download a metadata file from the NCBI but here is
a minimal specification if you want to use this on another source.

The file should be tab separated with a header row.  The header should
include the following as a minimum.  Order isn't important:
- species_taxid
- taxid
- organism_name
- ftp_path

The organism name is used to guess the genus and species; the genus is
taken to be the first word before a space and the species to be the first
two words.

e.g. the organism name `Streptococcus pneumoniae R6` is parsed into the
following:
```
{
  'genus': 'streptococcus',
  'species': 'streptococcus_pneumoniae',
  'organism_name': 'streptococcus_pneumoniae_r6'
}
```

`ftp_path` should provide a URL such as [ftp://ftp.ncbi.nlm.nih.gov/genomes/all/GCA_000007045.1_ASM704v1](ftp://ftp.ncbi.nlm.nih.gov/genomes/all/GCA_000007045.1_ASM704v1) which should include the following files as a minimum:
- README.txt
- md5checksums.txt
- GCA_000007045.1_ASM704v1_assembly_stats.txt
- GCA_000007045.1_ASM704v1_assembly_report.txt
- GCA_000007045.1_ASM704v1_genomic.fna.gz
- GCA_000007045.1_ASM704v1_genomic.gbff.gz
- GCA_000007045.1_ASM704v1_genomic.gff.gz

The accession ID is taken to be the last part of the `ftp_path`.

e.g. [ftp://ftp.ncbi.nlm.nih.gov/genomes/all/GCA_000007045.1_ASM704v1](ftp://ftp.ncbi.nlm.nih.gov/genomes/all/GCA_000007045.1_ASM704v1)
is parsed into an accession ID of `GCA_000007045.1_ASM704v1`
