#!/bin/bash
# Backup script for ALM server: dump databases and some of the important settings
# files into a tar file, and thence to an Amazon S3 bucket.

if [ `whoami` != 'root' ]; then
    echo "This script must be run as root."
    exit 1
fi

if [ `which s3cmd` = '' ]; then
    apt-get --yes install s3cmd
fi

export RAILS_ENV=production
export TZ=GMT0BST

install_dir=/var/www/alm/shared
backup_root=/tmp/db
backup_dir=${backup_root}/${tag}

tag=`date --utc +%Y%m%d_%H%M%S%1N`
s3prefix=`date --utc +%Y%m`
s3access=`grep -oP "(?<=\"s3access\": \")[^\"]+" $install_dir/config.json`
s3secret=`grep -oP "(?<=\"s3secret\": \")[^\"]+" $install_dir/config.json`
s3bucket=`grep -oP "(?<=\"s3bucket\": \")[^\"]+" $install_dir/config.json`

mysqldump_opts="--no-extended-insert --single-transaction --flush-logsi --create-options"
mysqldump_file="${backup_dir}/alm_${RAILS_ENV}_${tag}.sql"
couch_dumpdb="alm_${RAILS_ENV}_$tag"
couch_dumpfile="alm_${RAILS_ENV}_$tag.couch"
couch_url="http://localhost:5984"
couch_name=alm
headerct="Content-Type: application/json"
data="{ \"_id\": \"alm_rep_$tag\", \"source\": \"${couch_name}\", \"target\":  \"${couch_dumpdb}\" }"

# clean out old backups
mkdir -p $backup_root
rm -rf $backup_root/*

# this is our directory
mkdir -p $backup_dir

cp $install_dir/config.json $backup_dir
cp $install_dir/config/settings.yml $backup_dir
cp $install_dir/config/database.yml $backup_dir
cp $install_dir/config/deploy/$RAILS_ENV.rb $backup_dir

starttime=`date +%s`
# stop/restart the service to avoid inconsistency
service apache2 stop

# backup mysql to sql file
mysqldump -uroot -pLFMxwQKHDt9pe9t alm_$RAILS_ENV >$mysqldump_file

# make new db for replicant
curl -s -X PUT ${couch_url}/${couch_dumpdb} | grep -q "\"error\"" 
if [ $? -eq 0 ]; then
   echo "Failed to create couch replica DB!".
fi
# replicate to it
curl -s -X POST -H "$headerct" -d "$data" ${couch_url}/_replicate | grep -q "\"error\"" 
if [ $? -eq 0 ]; then
   echo "Failed to replicate create couch DB!".
fi

# can restart the service now
service apache2 start
endtime=`date +%s`

echo Backup took $((endtime - starttime)) seconds

cp /var/lib/couchdb/${couch_dumpfile} $backup_dir
curl -s -X DELETE ${couch_url}/${couch_dumpdb}

tar cfz $backup_root/$tag.tgz -C $backup_dir .

s3cmd --access_key="$s3access" --secret_key="$s3secret" mb s3://$s3bucket
s3cmd --access_key="$s3access" --secret_key="$s3secret" put $backup_root/$tag.tgz s3://$s3bucket/$s3prefix
s3cmd --access_key="$s3access" --secret_key="$s3secret" ls -H s3://$s3bucket/$s3prefix

rm -f $mysqldump_file
rm -f $backup_dir/$couch_dumpfile
rm -f $backup_dir/config.json
rm -f $backup_dir/settings.yml
rm -f $backup_dir/database.yml
rm -f $backup_dir/$RAILS_ENV.rb

exit 0

