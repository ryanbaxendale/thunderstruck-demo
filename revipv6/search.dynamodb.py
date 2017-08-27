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

def is_known(query=None):
	if query is not None:
		dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
		table = dynamodb.Table(table_name)
		response = table.get_item(Key={'query': query})
		if 'Item' in response:
			return True
		else:
			return False

#if not is_known(query='2.8.0.0.4.5.2.0.8.2.1.0.2.0.2.0.6.c.0.0.8.5.0.0.0.0.0.0.6.0.4.2.ip6.arpa.'):
#	print("this is unknown")


client = boto3.client('dynamodb', region_name='ap-southeast-1')
dynamodb_stats = client.describe_table(TableName=table_name)
total_items_in_dynamodb = dynamodb_stats['Table']['ItemCount']
print(str(total_items_in_dynamodb) + " items in dynamodb")

def scan_data(FilterExpression=None, limit=200):
	num_searched = 0
	last_eval_key = None
	percentage_complete = 0.0
	while True:
		if last_eval_key is not None:
			response = table.scan(
				Select='ALL_ATTRIBUTES',
				FilterExpression=FilterExpression,
				ExclusiveStartKey=last_eval_key,
				Limit=limit,
			)
		else:
			response = table.scan(
				Select='ALL_ATTRIBUTES',
				FilterExpression=FilterExpression,
				Limit=limit,
			)
		#num_searched = num_searched + int(response['ScannedCount'])
		#print(str(num_searched)+"/"+str(total_items_in_dynamodb))
		#percentage_complete = (float(num_searched) / float(total_items_in_dynamodb)) * 100
		#if int(percentage_complete % 20) == 0:
		#	print("STATUS: {:.0%}".format(percentage_complete))
		if 'Items' in response:
			for item in response['Items']:
				print(item['PTR']+" - "+item['query'])
		if 'LastEvaluatedKey' in response:
			last_eval_key = response['LastEvaluatedKey']
		else:
			break


dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
table = dynamodb.Table(table_name)

searchfor = sys.argv[1]
print("searching for: "+searchfor)
scan_data(limit=200, FilterExpression=Attr('PTR').contains(searchfor))

