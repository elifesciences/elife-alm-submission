# -*- coding: utf-8 -*-
#
# Scan an S3 bucket for 'files' containing XML conforming to the NLM document
# standard and read from them the DOI, publication date and document title for
# use as input to the PLoS Article Metrics Server application.
#
# Created 2014 Ruth Ivimey-Cook, eLife Sciences Ltd.
#

from __future__ import print_function
import re, sys, argparse, lxml, gc, htmlentitydefs
import parseNLM as nlm
from boto.s3.connection import S3Connection, Location
from boto.s3.key import Key
from boto.s3.keyfile import KeyFile
from zipfile import ZipFile, BadZipfile

settings=None

# using print_function
def debugmsg(*objs):
    """
    Print additional info to stderr iff the verbose flag has been enabled
    """
    if settings.verbose>1:
        print("DEBUG: ", *objs, end='\n', file=sys.stderr)

def infomsg(*objs):
    """
    Print additional info to stderr iff the verbose flag has been enabled
    """
    if settings.verbose:
        print("INFO: ", *objs, end='\n', file=sys.stderr)

def warningmsg(*objs):
    """
    Print warning message to stderr
    """
    print("WARNING: ", *objs, end='\n', file=sys.stderr)

def errormsg(*objs):
    """
    Print error message to stderr
    """
    print("ERROR: ", *objs, end='\n', file=sys.stderr)


def getoptions():
    """
    Use the Python argparse module to read in the command line args
    """
    parser = argparse.ArgumentParser(
        prog='s3artscan',
        description='Read an AWS/S3 article storage bucket and return a list of the articles.',
        usage='%(prog)s [options]'
        )
    parser.add_argument('--startdoi', help='first DOI reference to process (ascending numeric sort) e.g. eLife.00055', default='eLife.00000')
    parser.add_argument('--enddoi', help='last DOI reference to process (ascending numeric sort) e.g. eLife.00300', default='eLife.99999')
    parser.add_argument('--bucket', help='the name of the S3 storage bucket', default='elife-articles')
    parser.add_argument('--awssec', help='S3 access secret, or use env-var AWS_SECRET_ACCESS_KEY', default='')
    parser.add_argument('--awskey', help='S3 access key id, or use env-var AWS_ACCESS_KEY_ID', default='')
    parser.add_argument('--maxarts', help='maximum number of articles to print', type=int, default=99999)
    parser.add_argument('--earliest', help='earliest date to include article (YYYYMMDD) based on bucket dating')
    parser.add_argument('--latest', help='latest date to include article (YYYYMMDD) based on bucket dating')

    parser.add_argument('--verbose', '-v', action='count', help='print additional messages to stderr', default=0)
    parser.add_argument('--detailed', help='detailed output (not compatible with ALM)')

    args = parser.parse_args()
    if (args.startdoi != 'eLife.00000') or (args.enddoi != 'eLife.99999'):
        warningmsg( "Limiting articles by DOI: ", args.startdoi, args.enddoi )

    if (args.earliest is not None) or (args.latest is not None):
        warningmsg( "Limiting articles by S3Date: ", args.earliest, args.latest )

    return args

##
# Removes HTML or XML character references and entities from a text string.
#
# @param text The HTML (or XML) source text.
# @return The plain text, as a Unicode string, if necessary.

def unescape(text):
    def fixup(m):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text # leave as is
    return re.sub("&#?\w+;", fixup, text)



def fetchxml(awsbucketkey):
    """
    Given an AWS Key() into a bucket, fetch the contents of the XML file stored
    there as a single string.
    If the filename ends in .zip, assume it is a ZIP-encoded single file and return
    that.
    Returns None if the Key's name doesn't end .xml or .xml.zip
    """

    xmlcontent = None
    if awsbucketkey.name.endswith('.xml.zip'):
        try:
            infomsg(awsbucketkey.name + ' ...unzip')
            keyf = KeyFile(awsbucketkey)
            if keyf is None:
                errormsg('ERROR: Failed to open S3 bucket object: ' + awsbucketkey.name)
            else:
                try:
                    zf = ZipFile(keyf)
                    # get just the first file in archive,
                    # as there shouldn't ever be more than one
                    xmlfile = next(iter(zf.infolist()), None)
                    # orig filename and mtime: debugmsg(xmlfile.filename, xmlfile.date_time)
                    xmlcontent = zf.read(xmlfile)

                except BadZipfile as badz:
                    errormsg('ZIP Exception caught while reading zipped S3 file', badz.message)

        except Exception as exc:
            errormsg('Runtime Exception caught while reading zipped S3 file', exc.message)
            raise exc

    elif awsbucketkey.name.endswith('.xml'):
        try:
            infomsg(awsbucketkey.name)
            keyf = KeyFile(awsbucketkey)
            if keyf is None:
                errormsg('ERROR: Failed to open S3 bucket object: ' + awsbucketkey.name)
            else:
                xmlcontent = keyf.read()

        except Exception as exc:
            errormsg('ERROR: Exception caught while reading S3 file', exc.message)
            raise exc

    return xmlcontent 


def process(xmlcontent):
    """
    Given an NLM-formatted document in xmlcontent, extract the required information
    and print it on the standard output 
    """
    try:
        soup = nlm.parse_xml(xmlcontent)
        title = unescape(nlm.title(soup))
        doi = nlm.doi(soup)
        (pubdD, pubdM, pubdY) = nlm.get_pub_date_tuple(soup)
        print(u"{0} {1}-{2}-{3} {4}".format(doi, pubdY, pubdM, pubdD, title))

    except RuntimeError as runerr:
        errormsg('Runtime Exception caught while processing file', runerr.message)
    except Exception as exc:
        errormsg('Unexpected Exception caught while processing file', exc.message)


def isartancluded(filename):
    """
    Use the filename to determine the article number and hence the eLife DOI,
    and from that determine whether we should fetch and print the article info.
    """
    try:

        # There are 'files' corresponding to folders, and 'files' containing
        # PDF and other content: ignore them.

        if filename.endswith('.xml') or filename.endswith('.xml.zip'):

            if (settings.startdoi == 'eLife.00000') and (settings.enddoi == 'eLife.99999'):
                # default: include everything
                infomsg("Including ", filename, " (default)")
                return True
            else:
                # most articles have filenames like '00000/elife_2000_00000.xml.zip'
                pat = re.compile(r'(?P<prefix>[0-9]+)/elife_(?P<year>2[0-9]+)_(?P<artno>[0-9]+)')
                mat = pat.search(filename)
                if mat is None:

                    # a small number of articles have filenames like '00000/elife00000.xml'
                    pat = re.compile(r'(?P<prefix>[0-9]+)/elife(?P<artno>[0-9]+)')
                    mat = pat.search(filename)
                    if mat is None:
                        warningmsg("Bucket filename could not be parsed: is it really an article? ", filename)
                        return False

                my_eoi = u"eLife." + mat.group('artno')
                infomsg("Checking inclusion: ", my_eoi)

                if settings.startdoi <= my_eoi <= settings.enddoi:
                    infomsg("Including ", filename)
                    return True
                else:
                    debugmsg("Skipping ", filename)
                    return False
        else:
            return False

    except Exception as ex:
        errormsg("Cannot connect to AWS/S3", ex.message)


def getbucketlist():
    """
    Make a connection to the S3 bucket 
    """
    try:
        if settings.awskey > '' and settings.awssec > '':
            # Use command line specified access info
            conn = S3Connection(settings.awskey, settings.awssec)
        else:
            # Use env vars AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
            conn = S3Connection()
    except Exception as ex:
        errormsg("Cannot connect to AWS/S3", ex.message)
	return None

    if conn.lookup(settings.bucket) is None:
        errormsg("Cannot find S3 bucket", settings.bucket)
        bucket = None
    else:
        bucket = conn.get_bucket(settings.bucket)

    if bucket is not None:
        keys = bucket.list()
        return keys
    else:
        return None


def dobucketlist(keys):
    """
    Read in the files stored in the bucket and process them
    """
    numarts = settings.maxarts
    for k in keys:
        if isartancluded(k.name):
            xmlcontent = fetchxml(k)
            if xmlcontent is not None:
                process(xmlcontent)
                numarts -= 1
                if numarts <= 0:
                    break
        gc.collect()


def main():
    global settings
    settings = getoptions()
    keys = getbucketlist()
    if keys is not None:
        dobucketlist(keys)


try:
    if __name__ == "__main__":
        main()
except KeyboardInterrupt:
    sys.exit(1)

