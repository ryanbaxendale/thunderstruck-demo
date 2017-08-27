import os
import urllib2
my_ip = urllib2.urlopen('http://diagnostic.opendns.com/myip').read()
response = open(os.environ['res'], 'w')
response.write("Hello from azure functions "+str(my_ip))
response.close()
