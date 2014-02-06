from __future__ import print_function
import re
import sys
import argparse
import lxml
import parseNLM as nlm
from boto.s3.connection import S3Connection, Location
from boto.s3.key import Key
from boto.s3.keyfile import KeyFile
from zipfile import ZipFile

# Global options
verbose=1
bucketname='elife-articles'
accessid=''
secretkey=''
startdoi='eLife.00000'
enddoi=  'eLife.99999'

# using print_function
def debugmsg(*objs):
    """
    Print additional info to stderr iff the verbose flag has been enabled
    """
    if verbose>1:
        print("DEBUG: ", *objs, end='\n', file=sys.stderr)

def infomsg(*objs):
    """
    Print additional info to stderr iff the verbose flag has been enabled
    """
    if verbose:
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
    print("WARNING: ", *objs, end='\n', file=sys.stderr)


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

    parser.add_argument('--verbose', '-v', action='count', help='print additional messages to stderr', default=0)

    args = parser.parse_args()
    global accessid
    global secretkey
    global verbose
    global bucketname
    global startdoi
    global enddoi
    accessid = args.awskey
    secretkey= args.awssec
    verbose = args.verbose
    bucketname = args.bucket
    startdoi = args.startdoi
    enddoi = args.enddoi
    if (startdoi != 'eLife.00000') or (enddoi != 'eLife.99999'):
        infomsg( "Limiting articles: ", startdoi, enddoi )

def fetchxml(awsbucketkey):
    """
    Given an AWS Key() into a bucket, fetch the contents of the XML file stored
    there as a single string.
    If the filename ends in .zip, assume it is a ZIP-encoded single file and return
    that.
    Returns None if the Key's name doesn't end .xml or .xml.zip
    """

    xmlcontent=None
    if awsbucketkey.name.endswith('.xml.zip'):
	infomsg(awsbucketkey.name + ' ...unzip')
	keyf = KeyFile(awsbucketkey)
	if (keyf is None):
	    errormsg('ERROR: Failed to open S3 bucket object: ' + awsbucketkey.name)
	else:
	    zf = ZipFile(keyf)
	    # get just the first file in archive,
	    # as there shouldn't ever be more than one
	    xmlfile = next(iter(zf.infolist()), None)
	    # orig filename and mtime: debugmsg(xmlfile.filename, xmlfile.date_time)
	    xmlcontent = zf.read(xmlfile)

    elif awsbucketkey.name.endswith('.xml'):
	infomsg( awsbucketkey.name )
	keyf = KeyFile(awsbucketkey)
	if (keyf is None):
	    errormsg('ERROR: Failed to open S3 bucket object: ' + awsbucketkey.name)
	else:
	    xmlcontent = keyf.read()

    return xmlcontent 


def process(xmlcontent):
    """
    Given an NLM-formatted document in xmlcontent, extract the required information
    and print it on the standard output 
    """
    soup = nlm.parse_xml(xmlcontent)
    title = nlm.title(soup)
    doi = nlm.doi(soup)
    (pubdD, pubdM, pubdY) = nlm.get_pub_date_tuple(soup)
    print("{0} {1}-{2}-{3} {4}".format(doi,pubdY,pubdM,pubdD,title)) 


def isArtIncluded(filename):
    """
    Use the filename to determine the article number and hence the eLife DOI,
    and from that determine whether we should fetch and print the article info.
    """

    # There are 'files' corresponding to folders, and 'files' containing
    # PDF and other content: ignore them.

    if filename.endswith('.xml') or filename.endswith('.xml.zip'):

        if (startdoi == 'eLife.00000') and (enddoi == 'eLife.99999'):
            # default: include everything
	    infomsg("Including ", filename, " (default)" )
	    return True
        else:
	    # most articles have filenames like '00000/elife_2000_00000.xml'
	    pat = re.compile(r'(?P<prefix>[0-9]+)/elife_(?P<year>2[0-9]+)_(?P<artno>[0-9]+)')
	    mat = pat.search(filename)
	    if mat is None:

		# a small number of articles have filenames like '00000/elife00000.xml'
		pat = re.compile(r'(?P<prefix>[0-9]+)/elife(?P<artno>[0-9]+)')
		mat = pat.search(filename)

		if mat is None:
		    warningmsg("Bucket filename could not be parsed: is it really an article? ", filename)
		    return False

	    my_eoi = "eLife." + mat.group('artno') 
	    infomsg( "Checking inclusion: ", my_eoi)

	    if (my_eoi >= startdoi and my_eoi <= enddoi):
		infomsg("Including ", filename)
		return True
	    else:
		debugmsg("Skipping ", filename)
		return False
    else:
        debugmsg("Skipping ", filename)
	return False


def getbucketlist():
    """
    Make a connection to the S3 bucket 
    """

    try:
	if (accessid>'' and secretkey>''):
	    # Use command line specified access info
	    conn = S3Connection(accessid, secretkey)
	else:
	    # Use env vars AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
	    conn = S3Connection()
    except():
	errormsg("Cannot connect to AWS/S3")

    if conn.lookup(bucketname) is None:
	errormsg("Cannot find S3 bucket", bucketname)
    else:
	bucket = conn.get_bucket(bucketname)

    keys=bucket.list()
    return keys
 

def dobucketlist(keys):
    """
    Read in the files stored in the bucket and process them
    """
    for k in keys:
        #infomsg("Listed: ", k.name)

	if isArtIncluded(k.name):
	    xmlcontent = fetchxml(k)
	    if xmlcontent != None and len(xmlcontent) >0:
		process(xmlcontent)


def main():
    getoptions()
    keys=getbucketlist()
    dobucketlist(keys)


if __name__ == "__main__":
    main()
