# Elife Article Metrics Server Support Utilities

## S3Artscan

This python program uses Amazon S3 via 'boto' to read articles from the eLife
article store and parse them for DOI and title information using the NLM parser,
printing the result out in a format suitable for the alm server db:article:load
call. Use --help for info on parameters.

# ALMBackup / ALMRestore

These shell scripts work as a pair to save and restore the ALM database to a tar
file stored in an S3 bucket. Along with the SQL and Couch databases, several of
the more important settings files are saved (but not restored) in case of need.

ALMbackup configuration is all via variables in the code except for the AWS
credentials needed to access the S3 bucket, which are expected to be in the
config.json file of the ALM server (in /var/www/alm/shared).

ALMrestore uses the same credentials from config.json, and accepts a single
command-line argument which is the name of the object to restore from, in the
form: s3://bucket-name/yymm/yymmdd_hhmmsst.tgz (which is the format used
to save data by backup).


