import sys
from urllib.request import urlopen
def main(dict):
    my_ip = urlopen('http://diagnostic.opendns.com/myip').read()
    print("Hello from openwhisk functions "+str(my_ip))
    return {'ip': str(my_ip)}
