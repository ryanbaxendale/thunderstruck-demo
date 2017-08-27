#!/usr/bin/env pypy

# include the lib folder when searching for libraries
import sys
sys.path.insert(0, 'lib')
import site
site.addsitedir("lib")

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

# boto3
import boto3
import botocore
from boto3.dynamodb.conditions import Key, Attr
from botocore.client import Config

import datetime
#import pytz
#tz = pytz.timezone('Asia/Singapore')
tz = None

import multiprocessing
import math

# lambda config
lambda_function_name = "revipv6"
lambda_aws_access_key = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
lambda_aws_secret_key = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
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

# safe value is 4
processes = multiprocessing.cpu_count() * 6

# lets use 8, 12, 16, 20, 24, 28, 32, 48, 64
# max ipv6.arpa is 73
max_depth = 73

# max number of functions to call when running out of time
max_runs = 25

table_name = 'thunderstruck-revipv6'
lookups_per_worker = 1
dns_server_list = [
	'109.69.8.51',
	'156.154.70.1',
	'156.154.71.1',
	'193.183.98.154',
	'195.46.39.39',
	'195.46.39.40',
	'198.101.242.72',
	'199.85.126.10',
	'199.85.127.10',
	'208.67.220.220',
	'208.67.222.222',
	'208.76.50.50',
	'208.76.51.51',
	'209.244.0.3',
	'209.244.0.4',
	'216.146.35.35',
	'216.146.36.36',
	'23.253.163.53',
	'37.235.1.174',
	'37.235.1.177',
	'64.6.64.6',
	'64.6.65.6',
	'74.82.42.42',
	'77.88.8.1',
	'77.88.8.8',
	'81.218.119.11',
	'8.20.247.20',
	'8.26.56.26',
	'84.200.69.80',
	'84.200.70.40',
	'8.8.4.4',
	'8.8.8.8',
	'89.233.43.71',
	'91.239.100.100',
	'96.90.175.167',
]
blacklist = ["6to4;2.0.0.2.ip6.arpa.?"]


def start_with_dynamodb_data(config=None, limit=200):
	# now get all the ipv6 arpa items from dynamodb
	dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
	table = dynamodb.Table(table_name)
	FilterExpression=Attr('query').exists()

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
		if 'Items' in response:
			for item in response['Items']:
				target_ipv6 = item['query']
				# build the task
				config['ipv6_prefixes'] = [target_ipv6]
				task = {}
				task['commands'] = config.copy()
				if (len(target_ipv6) + max_depth) > 73:
					task['commands']['max_depth'] = 73
				else:
					task['commands']['max_depth'] = len(target_ipv6) + max_depth
				task['region'] = random.choice(regions_with_function)
				#pprint.pprint(task)
				# trigger worker to start this search
				run_worker(task)
				# store it in text file
				print(target_ipv6)
				with open('ipv6_revlist_dynamodb.txt', 'a') as ipv6_revlist_dynamodb:
					ipv6_revlist_dynamodb.write("%s\n" % target_ipv6)
				ipv6_revlist_dynamodb.close()
		if 'LastEvaluatedKey' in response:
			last_eval_key = response['LastEvaluatedKey']
		else:
			break
	


def send_worker_task(commands, region=None):
	try:
		commands = json.dumps(commands)
		client = boto3.client('lambda',
			region_name=region,
			aws_access_key_id=lambda_aws_access_key,
			aws_secret_access_key=lambda_aws_secret_key,
			)
		client.invoke(
			FunctionName=lambda_function_name,
			InvocationType='Event',
			LogType='None',
			Payload=commands,
		)
		return True
	except Exception as e:
		print "Unexpected error"
		print e
		print traceback.format_exc()
		return False


def run_worker(task):
	# keep trying in case of error
	success = False
	while not success:
		success = send_worker_task(commands=task['commands'], region=task['region'])


config = {}
config['blacklist'] = blacklist
config['dns_server_list'] = dns_server_list
config['table_name'] = table_name
config['run_number'] = 1
config['max_runs'] = max_runs

# this will use dynamodb data and start searching deeper
start_with_dynamodb_data(config=config)


# this will go through all items in the file 
# open ipv6_revlist
ipv6_prefixes = []
with open('ipv6_revlist_dynamodb.txt', 'r') as ipv6_revlist_backup:
	ipv6_prefixes = ipv6_revlist_backup.read().splitlines()
ipv6_revlist_backup.close()

#ipv6_prefixes = ipv6_prefixes[1:3]
#print ipv6_prefixes

# sample starting points for testing
#ipv6_prefixes = ['8.6.0.0.0.0.0.0.0.0.0.0.0.0.0.0.2.0.c.0.3.0.0.4.0.0.8.6.4.0.4.2.ip6.arpa.']
#ipv6_prefixes = ['0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa.']
#ipv6_prefixes =  ['0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa.']
# sample responses:
#{"ARPA": "0.8.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa.", "QUESTION": "0.8.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. IN PTR", "AUTHORITY": "", "CNAME": "", "runid": 1499875200, "error": false, "ANSWER": "0.8.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. 6856 IN PTR l7lb.cloud.wide.ad.jp.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa.", "PTR": "l7lb.cloud.wide.ad.jp.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa.", "metadata": {"rcode": "NOERROR", "opcode": "QUERY", "id": "16450", "flags": "QR RD RA"}}
#{"ARPA": "1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa.", "QUESTION": "1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. IN PTR", "AUTHORITY": "", "CNAME": "", "runid": 1499875200, "error": false, "ANSWER": "1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. 6860 IN PTR ns1.v6.wide.ad.jp.", "PTR": "ns1.v6.wide.ad.jp.", "metadata": {"rcode": "NOERROR", "opcode": "QUERY", "id": "10260", "flags": "QR RD RA"}}
#{"ARPA": "3.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa.", "QUESTION": "3.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. IN PTR", "AUTHORITY": "", "CNAME": "", "runid": 1499875200, "error": false, "ANSWER": "3.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. 7199 IN PTR nons.wide.ad.jp.", "PTR": "nons.wide.ad.jp.", "metadata": {"rcode": "NOERROR", "opcode": "QUERY", "id": "4961", "flags": "QR RD RA"}}
#{"ARPA": "4.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa.", "QUESTION": "4.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. IN PTR", "AUTHORITY": "", "CNAME": "", "runid": 1499875200, "error": false, "ANSWER": "4.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. 7199 IN PTR ns.wide.ad.jp.", "PTR": "ns.wide.ad.jp.", "metadata": {"rcode": "NOERROR", "opcode": "QUERY", "id": "13405", "flags": "QR RD RA"}}
#{"ARPA": "5.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa.", "QUESTION": "5.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. IN PTR", "AUTHORITY": "", "CNAME": "", "runid": 1499875200, "error": false, "ANSWER": "5.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. 7199 IN PTR www2.wide.ad.jp.", "PTR": "www2.wide.ad.jp.", "metadata": {"rcode": "NOERROR", "opcode": "QUERY", "id": "23495", "flags": "QR RD RA"}}
#{"ARPA": "6.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa.", "QUESTION": "6.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. IN PTR", "AUTHORITY": "", "CNAME": "", "runid": 1499875200, "error": false, "ANSWER": "6.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. 7199 IN PTR newns.tokyo.wide.ad.jp.", "PTR": "newns.tokyo.wide.ad.jp.", "metadata": {"rcode": "NOERROR", "opcode": "QUERY", "id": "351", "flags": "QR RD RA"}}
#{"ARPA": "7.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa.", "QUESTION": "7.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. IN PTR", "AUTHORITY": "", "CNAME": "", "runid": 1499875200, "error": false, "ANSWER": "7.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. 7199 IN PTR mail.wide.ad.jp.", "PTR": "mail.wide.ad.jp.", "metadata": {"rcode": "NOERROR", "opcode": "QUERY", "id": "56974", "flags": "QR RD RA"}}
#{"ARPA": "8.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa.", "QUESTION": "8.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. IN PTR", "AUTHORITY": "", "CNAME": "", "runid": 1499875200, "error": false, "ANSWER": "8.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. 7199 IN PTR ns.tokyo.wide.ad.jp.", "PTR": "ns.tokyo.wide.ad.jp.", "metadata": {"rcode": "NOERROR", "opcode": "QUERY", "id": "42001", "flags": "QR RD RA"}}
#{"ARPA": "9.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa.", "QUESTION": "9.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. IN PTR", "AUTHORITY": "", "CNAME": "", "runid": 1499875200, "error": false, "ANSWER": "9.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. 7199 IN PTR ns.nara.wide.ad.jp.", "PTR": "ns.nara.wide.ad.jp.", "metadata": {"rcode": "NOERROR", "opcode": "QUERY", "id": "7565", "flags": "QR RD RA"}}
#{"ARPA": "a.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa.", "QUESTION": "a.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. IN PTR", "AUTHORITY": "", "CNAME": "", "runid": 1499875200, "error": false, "ANSWER": "a.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. 6860 IN PTR ftp-netbsd.tokyo.wide.ad.jp.", "PTR": "ftp-netbsd.tokyo.wide.ad.jp.", "metadata": {"rcode": "NOERROR", "opcode": "QUERY", "id": "62941", "flags": "QR RD RA"}}
#{"ARPA": "c.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa.", "QUESTION": "c.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. IN PTR", "AUTHORITY": "", "CNAME": "", "runid": 1499875200, "error": false, "ANSWER": "c.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. 7199 IN PTR moca.wide.ad.jp.", "PTR": "moca.wide.ad.jp.", "metadata": {"rcode": "NOERROR", "opcode": "QUERY", "id": "9580", "flags": "QR RD RA"}}
#{"ARPA": "d.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa.", "QUESTION": "d.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. IN PTR", "AUTHORITY": "", "CNAME": "", "runid": 1499875200, "error": false, "ANSWER": "d.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. 7199 IN PTR www3.wide.ad.jp.", "PTR": "www3.wide.ad.jp.", "metadata": {"rcode": "NOERROR", "opcode": "QUERY", "id": "8482", "flags": "QR RD RA"}}
#{"ARPA": "f.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa.", "QUESTION": "f.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. IN PTR", "AUTHORITY": "", "CNAME": "", "runid": 1499875200, "error": false, "ANSWER": "f.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. 7199 IN PTR ns-wide.wide.ad.jp.", "PTR": "ns-wide.wide.ad.jp.", "metadata": {"rcode": "NOERROR", "opcode": "QUERY", "id": "17932", "flags": "QR RD RA"}}
#{"ARPA": "1.1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa.", "QUESTION": "1.1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. IN PTR", "AUTHORITY": "", "CNAME": "", "runid": 1499875200, "error": false, "ANSWER": "1.1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.0.0.0.0.0.0.0.0.0.2.0.1.0.0.2.ip6.arpa. 6859 IN PTR ns.fujisawa.wide.ad.jp.", "PTR": "ns.fujisawa.wide.ad.jp.", "metadata": {"rcode": "NOERROR", "opcode": "QUERY", "id": "19470", "flags": "QR RD RA"}}


workers = math.ceil(float(len(ipv6_prefixes)) / float(lookups_per_worker))
print("Need to spawn {workers} workers to lookup {ipv6_prefixes} with {lookups_per_worker} lookups per worker".format(
	workers=workers,
	ipv6_prefixes=len(ipv6_prefixes),
	lookups_per_worker=lookups_per_worker)
)

raw_input("continue?")

print(str(datetime.datetime.now(tz)) + " - starting revipv6")
start_time = datetime.datetime.now(tz)
i = 0
region_picker = 0
tasklist = []
while i < len(ipv6_prefixes):
	config['ipv6_prefixes'] = ipv6_prefixes[i:i + lookups_per_worker]
	i = i + lookups_per_worker
	task = {}
	task['commands'] = config.copy()
	if (len(config['ipv6_prefixes'][0]) + max_depth) > 73:
		task['commands']['max_depth'] = 73
	else:
		task['commands']['max_depth'] = len(config['ipv6_prefixes'][0]) + max_depth
	task['region'] = regions_with_function[region_picker]
	tasklist.append(task)
	region_picker += 1
	if region_picker >= len(regions_with_function):
		region_picker = 0
start_time_workers = datetime.datetime.now(tz)
print(str(datetime.datetime.now(tz)) + " - starting workers")
# now start the workers in parallel
# this might make it take up a lot of memory
# split the tasks over the available processors
splittasks = len(tasklist) / processes

pool = multiprocessing.Pool(processes=processes, maxtasksperchild=splittasks)
pool.map_async(run_worker, tasklist)
pool.close()
pool.join()



"""
# this is to continue from a specific ip
continue_from_ipv6 = '6.0.0.0.0.0.5.0.1.0.0.2.ip6.arpa'
startfromhere = False
startregion = None

for task in tasklist:
	if continue_from_ipv6 in task['commands']['ipv6_prefixes']:
		startfromhere = True
		startregion = task['region']
		print("starting with region: "+startregion)
	if startfromhere:
		if startregion is not None and startregion == task['region']:
			dynamodb = boto3.client('dynamodb', region_name='ap-southeast-1')
			dynamodb_stats = dynamodb.describe_table(TableName='thunderstruck-revipv6')
			print(str(dynamodb_stats['Table']['ItemCount']) + " items in dynamodb")
		print(str(task['commands']['ipv6_prefixes']) + " - " + task['region'])
		run_worker(task)
"""		


end_time_workers = datetime.datetime.now(tz)
print(str(datetime.datetime.now(tz)) + " - done starting workers")
print("finished starting workers in " + str(end_time_workers - start_time_workers))

dynamodb = boto3.client('dynamodb', region_name='ap-southeast-1')
dynamodb_stats = dynamodb.describe_table(TableName='thunderstruck-revipv6')
print(str(dynamodb_stats['Table']['ItemCount']) + " items in dynamodb")

end_time = datetime.datetime.now(tz)
print("revipv6 finished in " + str(end_time - start_time))
