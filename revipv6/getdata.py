#!/usr/bin/env python
# include the lib folder when searching for libraries
import sys
sys.path.insert(0, 'lib')
import site
site.addsitedir("lib")

import boto3
from boto3.dynamodb.conditions import Key, Attr

import pprint
from bgpdumpy import BGPDump

import requests
import multiprocessing
import datetime
import glob
import random

import os
import netaddr

from dns import message, query, exception
import sys
import json
import hashlib
import re
import logging

table_name = 'thunderstruck-revipv6'

ipv6_prefixes = []
ipv6_revlist = []

def download_file(url=None, filename=None):
	# NOTE the stream=True parameter
	r = requests.get(url, stream=True)
	with open(filename, 'wb') as f:
		for chunk in r.iter_content(chunk_size=1024): 
			if chunk: # filter out keep-alive new chunks
				f.write(chunk)

# shorten .ip6.arpa. entry according to prefix length
def get_short(ipv6obj,mask):
	return ipv6obj.reverse_dns[(128-int(mask))/2:].strip('.')

# print ip6.arpa. zone for prefix
def print_unaligned(prefix, mask, short, ipv6obj):
	bits = 2**(4 - int(mask) % 4)
	char = ['0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f']
	last = char.index(get_short(ipv6obj, int(mask) + (4 - int(mask) % 4))[0])
	retval = ""
	for i in range (last,bits+last):
		retval = char[i]+'.'+short
	return retval

def print_prefix(prefix, mask):
	try:
		retvals = []
		# try to transform prefix into an object readable by netaddr
		ipv6obj = ''
		if len(prefix.split(':')) > 8:
			ipv6obj = netaddr.IPAddress(prefix[:-1]+'0')
		elif not prefix[:-1] == ':':
			ipv6obj = netaddr.IPAddress(prefix)
		else:
			ipv6obj = netaddr.IPAddress(prefix+'0')
		short = get_short(ipv6obj, mask)
		retvals.append(short)
		# handle masks not % 4, i.e. not ending on nibble boundary
		if not int(mask) % 4 == 0:
			retvals.append(print_unaligned(prefix, mask, short, ipv6obj))
		return retvals
	except Exception, e:
		sys.stderr.write(i)
		sys.stderr.write(str(e))

# determine if the prefix is unicast, funny way due to $old netaddr versions on scientific linux
def check_net(ipnet):
	net = netaddr.IPNetwork(unicode(ipnet))
	if not (net.is_link_local() or net.is_loopback() or net.is_ipv4_compat() or net.is_ipv4_mapped() or net.is_private() or net.is_multicast() or net.is_reserved()):
		if net.prefixlen > 12:
			return True
		else:
			return False
	else:
		return False

# Hosts from RIPE BGP collection
ripehosts=['rrc16','rrc15','rrc14','rrc13','rrc12','rrc11','rrc10','rrc09','rrc08','rrc07','rrc06','rrc05','rrc04','rrc03','rrc02','rrc01','rrc00']
pool = multiprocessing.Pool(processes=len(ripehosts))
for i in ripehosts:
	pool.apply_async(download_file, kwds={
		'url': "http://data.ris.ripe.net/"+str(i)+"/latest-bview.gz",
		'filename': "data/"+str(i)+".gz",
		})
pool.close()
pool.join()

# RouteViews Route Collectors
rviews=['route-views.eqix','route-views.isc','route-views.kixp','route-views.jinx','route-views.linx','route-views.nwax','route-views.telxatl','route-views.wide','route-views.sydney','route-views.saopaulo','route-views.sg','route-views.perth','route-views.sfmix','route-views.soxrs']
list_of_routeviews = requests.get("http://archive.routeviews.org/route-views.nwax/bgpdata/"+str(datetime.date.today().strftime("%Y.%m"))+"/RIBS/").text
for item in list_of_routeviews.split("a href="):
	routeview_latest = item[1:item.find("\">")]
pool = multiprocessing.Pool(processes=len(rviews))
for i in rviews:
	pool.apply_async(download_file, kwds={
		'url': "http://archive.routeviews.org/"+str(i)+"/bgpdata/"+str(datetime.date.today().strftime("%Y.%m"))+"/RIBS/"+str(routeview_latest),
		'filename': "data/"+str(i)+".bz2",
		})
pool.close()
pool.join()


# process the ripehosts data
for bviewfile in glob.glob("data/*.gz"):
	try:
		print "processing "+bviewfile
		with BGPDump(bviewfile) as bgp:
			for entry in bgp:
				if ":" in entry.body.prefix:
					prefix = str(entry.body.prefix)+"/"+str(entry.body.prefixLength)
					if check_net(prefix):
						if prefix not in ipv6_prefixes:
							ipv6_prefixes.append(prefix)
		print "got "+str(len(ipv6_prefixes))
	except Exception, e:
		print e

# now process the rviews data
for bviewfile in glob.glob("data/*.bz2"):
	try:
		print "processing "+bviewfile
		with BGPDump(bviewfile) as bgp:
			for entry in bgp:
				if ":" in entry.body.prefix:
					prefix = str(entry.body.prefix)+"/"+str(entry.body.prefixLength)
					if check_net(prefix):
						if prefix not in ipv6_prefixes:
							ipv6_prefixes.append(prefix)
		print "got "+str(len(ipv6_prefixes))
	except Exception, e:
		print e

# for each prefix splitt off mask an process
for i in ipv6_prefixes:
	prefix, mask = i.split('/')
	for retval in print_prefix(prefix, mask):
		if retval not in ipv6_revlist:
			ipv6_revlist.append(retval)

print "got "+str(len(ipv6_revlist)+" from bgp routing info")

# backup ipv6_revlist
with open('ipv6_revlist_backup.txt', 'w') as ipv6_revlist_backup:
	for item in ipv6_revlist:
		ipv6_revlist_backup.write("%s\n" % item)
ipv6_revlist_backup.close()

