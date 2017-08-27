import urllib2
def lambda_handler(event, context):
    response = urllib2.urlopen('http://diagnostic.opendns.com/myip').read()
    return 'Hello from Lambda'+str(response)
