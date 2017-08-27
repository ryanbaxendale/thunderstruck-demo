#!/bin/bash
# delete the old zip file
rm lambda_upload.zip
# delete unnecessary python library folders
find . -maxdepth 1 -type d | grep "\.dist-info$" | xargs rm -rf
# change permissions so its world readable or else you get strange errors in lambda
chmod a+r worker.py
chmod a+rx lib
find ./lib -type f -exec chmod a+r {} \;
find ./lib -type d -exec chmod a+rx {} \;
find ./lib -type d -exec chmod -R a+r {} \;
# now create the zip with all the folders in this folder
zip -r lambda_upload.zip lib worker.py
echo "now upload lamdba_upload.zip to aws lambda function"
