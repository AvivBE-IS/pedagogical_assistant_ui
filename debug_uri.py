import os, threading
from dotenv import load_dotenv
load_dotenv(r'.env')
uri = os.getenv('MONGODB_URI', '').strip()
host_uri = uri.split('@')[1].split('/')[0]

hardcoded = 'pedalogicalassisstant.fqwfon4.mongodb.net'

with open('compare_debug.txt', 'w', encoding='ascii', errors='replace') as f:
    f.write('host_uri len={}\n'.format(len(host_uri)))
    f.write('hardcoded len={}\n'.format(len(hardcoded)))
    f.write('equal: {}\n'.format(host_uri == hardcoded))
    f.write('host_uri hex: {}\n'.format(host_uri.encode('utf-8').hex()))
    f.write('hardcoded hex: {}\n'.format(hardcoded.encode('utf-8').hex()))
    for i, (a, b) in enumerate(zip(host_uri, hardcoded)):
        if a != b:
            f.write('DIFF at pos {}: {:04x} vs {:04x}\n'.format(i, ord(a), ord(b)))
    if len(host_uri) != len(hardcoded):
        f.write('LENGTH DIFF: host={} hard={}\n'.format(len(host_uri), len(hardcoded)))

print('done - check compare_debug.txt')
