elife-alm-submission
====================

Code supporting submission of articles to the ALM server.



s3artscan
---------
Scan the elife-articles bucket to get a list of the DOI, pubdate and title for each article published.

Requirements:

boto >= 2.4 (Amazon python/S3 API)
lxml 
parseNLM

usage: s3artscan [options]

Read an AWS/S3 article storage bucket and return a list of the articles.

optional arguments:
  -h, --help           show this help message and exit
  --startdoi STARTDOI  first DOI reference to process (ascending numeric sort)
                       e.g. eLife.00055
  --enddoi ENDDOI      last DOI reference to process (ascending numeric sort)
                       e.g. eLife.00300
  --bucket BUCKET      the name of the S3 storage bucket
  --awssec AWSSEC      S3 access secret, or use env-var AWS_SECRET_ACCESS_KEY
  --awskey AWSKEY      S3 access key id, or use env-var AWS_ACCESS_KEY_ID
  --verbose, -v        print additional messages to stderr


For example:

$ bin/python s3artscan.py --startdoi eLife.00020 --enddoi eLife.00050
10.7554/eLife.00031 2012-10-30 Foggy perception slows us down
10.7554/eLife.00036 2013-09-03 Mammalian genes induce partially reprogrammed pluripotent stem cells in non-mammalian vertebrate and invertebrate species
10.7554/eLife.00049 2012-11-13 Sodium taurocholate cotransporting polypeptide is a functional receptor for human hepatitis B and D virus

