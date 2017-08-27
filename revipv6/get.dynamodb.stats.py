#!/usr/bin/env python
from __future__ import print_function
# include the lib folder when searching for libraries
import sys
sys.path.insert(0, 'worker_lib')
import site
site.addsitedir("worker_lib")

import boto3
from boto3.dynamodb.conditions import Key, Attr
from dns import message, query, exception
import sys
import json
import hashlib
import re
import logging
import datetime
import random
import multiprocessing
import pprint

table_name = 'thunderstruck-revipv6'

client = boto3.client('dynamodb', region_name='ap-southeast-1')
dynamodb_stats = client.describe_table(TableName=table_name)
total_items_in_dynamodb = dynamodb_stats['Table']['ItemCount']
print(str(total_items_in_dynamodb) + " items in dynamodb")

