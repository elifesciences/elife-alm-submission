#!/bin/bash

artfile=/tmp/articles.$$
sortedart=/tmp/sorted.$$
lastseen=/tmp/lastdoiseen

lastdoi=`cat $lastseen`
if [ -z "$lastdoi" ]; then
   starg=""
else
   starg="--startdoi $lastseen"
fi

maxarg="--maxarts 10"

bin/python s3artscan.py $starg $maxarg >$artfile
sort <$artfile >$sortedart
rake db::articles:load <$sortedart

tail -1 $sortedart |cut -c9-19 >$lastseen
