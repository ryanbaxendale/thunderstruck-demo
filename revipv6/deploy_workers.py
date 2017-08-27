#!/usr/bin/env python
# include the lib folder when searching for libraries
import sys
sys.path.insert(0, 'lib')
import site
site.addsitedir("lib")

import ipaddress
import json, base64, uuid, traceback
import time
import pprint
import argparse
import uuid
import glob
import random
import urllib2
import re, binascii
import random
import requests

# boto3
import boto3
import botocore
from botocore.client import Config

import datetime
import pytz
tz = pytz.timezone('Asia/Singapore')

import threading
from multiprocessing import Process
import math



# lambda config
lambda_function_name = "revipv6"
# aws regions
global regions_with_function

#regions_with_function = ['ap-southeast-1']

regions_with_function = [
'us-east-1',
'us-east-2',
'us-west-1',
'us-west-2',
'ca-central-1',
'eu-west-1',
'eu-west-2',
'eu-central-1',
'ap-southeast-1',
'ap-southeast-2',
'ap-northeast-1',
'ap-northeast-2',
'ap-south-1',
'sa-east-1'
]

lambda_aws_iam_username = "lambda"
lambda_aws_access_key = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
lambda_aws_secret_key = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
lambda_function_name = "revipv6"
lambda_function_handler = "worker.lambda_handler"
lambda_function_role = "arn:aws:iam::xxxxxxxxxxxx:role/lambda_basic_execution"
lambda_zipfile = "lambda_upload.zip"
lambda_s3bucket_name = "thunderstruck-revipv6" # must be a valid s3 bucket name (no _ etc)
lambda_s3bucket_key = "lambda_upload.zip"

# s3 credentials
s3_aws_access_key = lambda_aws_access_key
s3_aws_secret_key = lambda_aws_secret_key

timeout = 300
memsize = 128


def deploy_workers():
    #lambda_regions = boto3.session.Session().get_available_regions('lambda')
    lambda_regions = regions_with_function

    # create the lambda function in all possible regions
    for region in lambda_regions:
        print("uploading zip file: " + lambda_zipfile + " to bucket: " + lambda_s3bucket_name + '-' + region)
        with open(lambda_zipfile, 'rb') as data:
            # connect to s3
            s3_client = boto3.client('s3', config=Config(signature_version='s3v4',
                                                         s3={'use_accelerate_endpoint': True}),
                                     aws_access_key_id=s3_aws_access_key,
                                     aws_secret_access_key=s3_aws_secret_key,
                                     region_name=region)
            s3_client.upload_fileobj(data, lambda_s3bucket_name + '-' + region, lambda_s3bucket_key)
        # now create/update the lambda function in each region
        print("creating lambda function in region: " + region)
        lambda_client = boto3.client('lambda',
                                     aws_access_key_id=lambda_aws_access_key,
                                     aws_secret_access_key=lambda_aws_secret_key,
                                     region_name=region)
        try:
            response = lambda_client.create_function(
                FunctionName=lambda_function_name,
                Runtime='python2.7',
                Role=lambda_function_role,
                Handler=lambda_function_handler,
                Code={
                    'S3Bucket': lambda_s3bucket_name + '-' + region,
                    'S3Key': lambda_s3bucket_key,
                },
                Timeout=timeout,
                MemorySize=memsize,
                Publish=False,
            )
            #pprint.pprint(response)
        except Exception:
            print("updating lambda function in region: " + region + " to use s3 object: "
                  + lambda_s3bucket_name + '-' + region + "/" + lambda_s3bucket_key)
            response = lambda_client.update_function_code(
                FunctionName=lambda_function_name,
                S3Bucket=lambda_s3bucket_name + '-' + region,
                S3Key=lambda_s3bucket_key,
                Publish=False,
            )
            response = lambda_client.update_function_configuration(
                FunctionName=lambda_function_name,
                Timeout=timeout,
                MemorySize=memsize,
            )
            #pprint.pprint(response)

def setup_s3_buckets():
    for region in regions_with_function:
	    # connect to s3
	    s3_client = boto3.client('s3', config=Config(signature_version='s3v4'),
	                             aws_access_key_id=lambda_aws_access_key,
	                             aws_secret_access_key=lambda_aws_secret_key,
	                             region_name=region)
	    target_bucket_name = lambda_s3bucket_name + '-' + region
	    print("setting up bucket " + target_bucket_name)
	    # check if the s3 bucket exists
	    list_buckets = s3_client.list_buckets()
	    #pprint.pprint(list_buckets)
	    has_bucket = False
	    for bucket in list_buckets['Buckets']:
	        if bucket['Name'] == target_bucket_name:
	            has_bucket = True
	    # create the bucket if it does not exist
	    if not has_bucket:
	        print("creating s3 bucket: " + target_bucket_name)
	        # handle the special case where region is us-east-1
	        if region == "us-east-1":
	            response = s3_client.create_bucket(
	                ACL='private',
	                Bucket=target_bucket_name,
	            )
	        else:
	            response = s3_client.create_bucket(
	                ACL='private',
	                Bucket=target_bucket_name,
	                CreateBucketConfiguration={
	                    'LocationConstraint': region,
	                },
	            )
	        #pprint.pprint(response)
	    # enable transfer acceleration
	    response = s3_client.put_bucket_accelerate_configuration(
	        Bucket=target_bucket_name,
	        AccelerateConfiguration={'Status': 'Enabled'}
	    )
	    pprint.pprint(response)
	    print("done setting up bucket "+target_bucket_name)

def delete_function():
    for region in regions_with_function:
        print("deleting lambda function in region: " + region)
        lambda_client = boto3.client('lambda',
                                     aws_access_key_id=lambda_aws_access_key,
                                     aws_secret_access_key=lambda_aws_secret_key,
                                     region_name=region)
        try:
            response = lambda_client.delete_function(FunctionName=lambda_function_name)
            pprint.pprint(response)
        except Exception as e:
            print("error deleteing function:", e)

#setup_s3_buckets()
deploy_workers()
#delete_function()

