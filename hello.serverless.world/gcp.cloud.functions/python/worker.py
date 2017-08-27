import urllib2
response = urllib2.urlopen('http://diagnostic.opendns.com/myip').read()
print 'Hello from google functions '+str(response)
