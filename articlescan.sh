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

bin/python s3artscan.py $starg >$artfile
sort <$artfile >$sortedart
rake db::articles:load <$sortedart

tail -1 $sortedart |cut -f1 >>$lastseen
