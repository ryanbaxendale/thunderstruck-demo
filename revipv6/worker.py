#!/usr/bin/env python
from __future__ import print_function
# include the lib folder when searching for libraries
import sys
sys.path.insert(0, 'worker_lib')
import site
site.addsitedir("worker_lib")

import boto3
from dns import message, query, exception
import sys
import json
import hashlib
import re
import logging
import datetime
import random
import multiprocessing

runid = int(datetime.date.today().strftime("%s"))
queries = 0
results = 0

global_config = None
global_context = None
procs = []

def lambda_handler(config=None, context=None):
	global global_config, global_context, ipv6_prefixes, max_depth, blacklist, dns_server_list, table_name, run_number, max_runs
	global_config = config
	global_context = context

	if config is not None:
		ipv6_prefixes = config['ipv6_prefixes']
		max_depth = config['max_depth']
		blacklist = config['blacklist']
		dns_server_list = config['dns_server_list']
		table_name = config['table_name']
		run_number = config['run_number']
		max_runs = config['max_runs']
	# run
	for start_from in ipv6_prefixes:
		if not check_autogen(start_from=start_from, limit=max_depth):
			start_search(start_from=start_from, limit=max_depth)

# return True if we only have 30s or less before being killed
def running_out_of_time(timeout=30000):
	global global_context
	remaining_ms = global_context.get_remaining_time_in_millis()
	if remaining_ms <= timeout:
		print("about to timeout: "+str(remaining_ms))
		return True
	return False

def start_search(start_from='', limit=0):
	if start_from.endswith('ip6.arpa'):
		start_from = start_from + '.'
	if start_from.endswith('ip6.arpa.'):
		blacklist_result = check_blacklist(start_from, blacklist)
		if blacklist_result:
			print("#base %s appears to be blacklisted for being handled by %s after %s queries" % (start_from, blacklist ,str(queries)))		
		else:
			if test_base(start_from):
				enum_all_subtree(start_from=start_from, limit=limit)
	#print("base: %s, queries done: %s, names found: %s" % (start_from, queries, results))

# obtain more interesting data from a DNS query
def parse_to_dict(r):
	d = str(r)
	ret = {'error':False,'runid':runid}
	for i in d.split(';'):
		cur = i.split('\n')
		if len(cur) > 1:
			try:
				if not cur[0][0] == 'i':
					ret[cur[0]] = cur[1]
					if cur[0] == 'ANSWER':
						ret['PTR'] = ''
						ret['CNAME'] = ''
						ptrdata = cur[1].split(' ')
						if ptrdata[-2] == 'PTR':
							ret['PTR'] = ptrdata[-1]
						else:
							ret['CNAME'] = ptrdata[-1]
				else:
					iddict = {}
					for j in cur:
						if j:
							idlist = j.split(' ')
							iddict[idlist[0]] = ' '.join(idlist[1:])
					ret['metadata'] = iddict
			except:
				ret['data'] = d
				ret['error'] = True
		elif not cur:
			ret[cur[0]] = ''
	# replace any blank items with 'null'
	for item in ret:
		if ret[item] is '':
			ret[item] = 'null'
	return ret

def tryquery(target):
	global queries
	# pick a random dns server
	dns_server = random.choice(dns_server_list)
	q = message.make_query(target, 'PTR')
	while True:
		try:
			queries = queries + 1
			response = query.udp(q, dns_server, timeout=2)
			return response
		except exception.Timeout:
			# change dns server if the current query timeout
			dns_server = random.choice(dns_server_list)
		except Exception:
			dns_server = random.choice(dns_server_list)

# here for historic reasons; used to write to a DB
def check_and_store_result(query=None, response=None):
	global results
	dict_data = parse_to_dict(response)
	dict_data['query'] = query
	# check that we have an ANSWER and ignore if not
	if dict_data['ANSWER'] is not 'null':
		results = results + 1
		#pprint.pprint(dict_data)
		print(query, dict_data['PTR'])
		#pprint.pprint(json.dumps(dict_data))
		#pprint.pprint(dict_data)
		attempts = 0
		while attempts < 5:
			try:
				dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
				table = dynamodb.Table(table_name)
				table.put_item(Item=dict_data)
				break
			except Exception:
				attempts = attempts + 1
				pass

def enum_all_subtree(start_from=None, limit=0):
	if len(start_from) <= limit:
		#print("enum start: "+str(start_from))
		for c in '0123456789abcdef':
			target = str(c+'.'+start_from)
			# check if we are running out of time in AWS Lambda, then start a new lambda worker
			if running_out_of_time():
				spawn_new_worker(start_from=target, limit=limit)
			# only query if we don't already know about this IP
			if not is_known(query=target):
				r = tryquery(target)
				# check if we got a response/reply to the PTR then store it
				check_and_store_result(query=target, response=r)
				if r.rcode() == 3:
					#print(target, len(target), "NXDOMAIN")
					# RFC1034 and RFC8020
					# NXDOMAIN - this is the end of the tree
					#print("reached the end of this tree")
					pass
				elif r.rcode() == 0:
					#print(target, len(target), "NOERROR")
					# NOERROR - search deeper
					#print("found something, enumerating")
					if len(target)+2 <= limit:
						# spawn a new process
						p = multiprocessing.Process(target=enum_all_subtree, kwargs={
							'start_from': target,
							'limit': limit,
						})
						procs.append(p)
						p.start()
						#enum_all_subtree(start_from=target, limit=limit)
						# spawn a new aws lambda worker
						#spawn_new_worker(start_from=target, limit=limit)
			#print("enum end: "+str(start_from))

def test_base(base):
	r = tryquery(base)
	if r.rcode() == 0:
		return 1
	else:
		return 0

def check_autogen(start_from=None, limit=0):
	add_length = (limit - len(start_from)) / 2
	if add_length < 4:
		#print("this is not autogen")
		return False
	cnt = 0
	for c in '0123456789abcdef':
		testbase = add_length * (c+".") + start_from
		cnt = cnt + test_base(testbase)
	if cnt >= 3:
		#print("this is autogen")
		return True
	else:
		#print("this is not autogen")
		return False

def check_blacklist(base, blacklist):
	for line in blacklist:
		name, regex = line.strip().split(';')
		r = re.compile(regex)
		if r.findall(base):
			return name
	return ""

def spawn_new_worker(start_from=None, limit=0):
	global run_number, max_runs, global_config, global_context
	if run_number+1 > max_runs:
		print("not spawning new worker as will be more than max run")
		print(global_config)
		sys.exit(1)
	commands = global_config.copy()
	commands['ipv6_prefixes'] = [start_from]
	commands['max_depth'] = limit
	commands['run_number'] = run_number + 1
	commands = json.dumps(commands)
	arn = global_context.invoked_function_arn.split(':')
	region = arn[3]
	lambda_function_name = arn[6]
	print("starting new lambda worker for:"+str(start_from))
	client = boto3.client('lambda',
		region_name=region,
		)
	response = client.invoke(
		FunctionName=lambda_function_name,
		InvocationType='Event',
		LogType='None',
		Payload=commands,
	)
	print("done: ",response)

def is_known(query=None):
	global table_name
	#print("checking if exists:"+str(query))
	if query is not None:
		dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
		table = dynamodb.Table(table_name)
		response = table.get_item(Key={'query': query})
		if 'Item' in response:
			return True
		else:
			return False
