import sys
import asyncio
from time import time
import re
import urllib.parse
import urllib.request
import json
import logging


# Utilities
CURR_SERVER_ID = None
CURR_SERVER = None
CLIENTS = {}


# Google Places API
URL = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json?'
KEY = 'AIzaSyAgBQsWyAz4U-S_Rs_BwVpWD_jnLLzzYoA'


class Server(object):
    def __init__(self, name, port, neighbors):
        self.name = name
        self.port = port
        self.neighbors = neighbors


SERVER_SETUP = {
    'Alford': Server('Alford',
        port=17630,
        neighbors=['Hamilton', 'Welsh']),
    'Ball': Server('Ball',
        port=17631,
        neighbors=['Holiday', 'Welsh']),
    'Hamilton': Server('Hamilton',
        port=17632,
        neighbors=['Holiday', 'Alford']),
    'Holiday': Server('Holiday',
        port=17633,
        neighbors=['Ball', 'Hamilton']),
    'Welsh': Server('Welsh',
        port=17634,
        neighbors=['Alford', 'Ball'])
}


SERVERS_PORTS = {
    'Alford':17630,
    'Ball':17631,
    'Hamilton':17632,
    'Holiday':17633,
    'Welsh':17634
}


class Client(object):
    def __init__(self, ID, coordinates, timestamp):
        self.ID = ID
        self.coordinates = coordinates
        self.timestamp = timestamp


@asyncio.coroutine
def main_server(reader, writer):
    logging.info('Connection started')

    message = yield from reader.read(100)
    data = message.decode()
    addr = writer.get_extra_info('peername')

    logging.info('Connected')
    logging.info('Received %r from %s' % (data, addr))

    data = data.split(' ')
    command = data[0]

    if command == 'IAMAT':
        new_client = get_client_info(data[1:])
        response = yield from iamat(new_client)
        yield from propagate_client(CURR_SERVER, response)

        logging.info('Send: %s' % response)

        writer.write(response.encode())
        yield from writer.drain()
    elif command == 'WHATSAT':
        try:
            client = CLIENTS[data[1]]
            radius = int(data[2])
            max_num = int(data[3])

            if radius < 0 or radius > 50:
                raise ValueError
            if max_num < 0 or max_num > 20:
                raise ValueError

            query = yield from whatsat(client, radius, max_num)
            search_results = yield from search(query)

            search_results['results'] = search_results['results'][:5]
            search_results = json.dumps(search_results, indent=3)

            response = yield from iamat(client)
            response = '\n'.join([response, search_results, '', ''])

            logging.info('Send: %s' % response)

            writer.write(response.encode())
            yield from writer.drain()
        except ValueError:
            error = '?' + ' ' + message
            logging.info('Invalid command')
            logging.info('Send: %s' % error)
            writer.write(message)
    elif command == 'AT':
        if data[3] in CLIENTS:
            return
        get_client_info(data[3:])
        
        logging.info('Connected')

        data[1] = CURR_SERVER_ID
        data = " ".join(data)
        yield from propagate_client(CURR_SERVER, data, data[1])
        return
    else:
        error = '?' + ' ' + message
        logging.info('Invalid command')
        logging.info('Send: %s' % error)
        writer.write(message)

    logging.info('Connection dropped')

def get_client_info(data):
    ID = data[0]
    coordinates = data[1]
    timestamp = float(data[2])

    CLIENTS[ID] = Client(
        ID,
        coordinates,
        timestamp)
    return CLIENTS[ID]

@asyncio.coroutine
def iamat(client):
    time_diff = time() - client.timestamp

    if time_diff > 0:
        time_diff = '+' + repr(time_diff)

    response = 'AT %s %s %s %s %s' %(
        CURR_SERVER_ID,
        time_diff,
        client.ID,
        client.coordinates,
        client.timestamp)

    return response

@asyncio.coroutine
def whatsat(client, radius, max_num_results):
    regex = r'([+-]\d+\.\d+)([+-]\d+\.\d+)'
    coordinates = re.sub(regex, r'\1,\2', client.coordinates)

    location = '&location=' + coordinates
    radius = '&radius=' + str(radius)
    key = '&key=' + KEY
    parameters = location + radius + key
    query = URL + parameters

    return query

@asyncio.coroutine
def search(url):
    parse = urllib.parse.urlparse(url)

    reader, writer = yield from asyncio.open_connection(
        parse.hostname,
        port=443,
        ssl=True)

    request = (
        'GET {url} HTTP/1.1\r\n'
        'Connection: close\r\n'
        '\r\n').format(url=url)

    logging.info('Connect to Google')
    writer.write(request.encode())
    yield from writer.drain()

    data = yield from reader.read()

    data = data.decode()
    data = data[data.index('{'):data.rindex('}') + 1]

    logging.info('Received: \n%s' % data)
    logging.info('Disconnect from Google')

    writer.close()
    return json.loads(data)

@asyncio.coroutine
def propagate_client(server, data, source=None):
    for n in server.neighbors:
        if n == source:
            continue
        yield from talk(SERVERS_PORTS[n], data)

@asyncio.coroutine
def talk(port, data):
    reader, writer = yield from asyncio.open_connection(
        'localhost',
        port)
    logging.info('Connected')
    logging.info('Send: %s' % data)

    writer.write(data.encode())
    logging.info('Disconnected')
    writer.close()

def main():
    # Start the server
    loop = asyncio.get_event_loop()
    coro = asyncio.start_server(main_server, 'localhost', CURR_SERVER.port, loop=loop)
    server = loop.run_until_complete(coro)

    logging.info('Start on port {}'.format(SERVERS_PORTS[CURR_SERVER_ID]))
    loop.run_forever()

    # Close the server
    server.close()
    loop.run_until_complete(server.wait_closed())
    logging.info('End')
    loop.close()

if __name__ == '__main__':
    try:
        CURR_SERVER_ID = sys.argv[1]
    except IndexError:
        sys.exit('Error: expected server argument\n'
                'Options:\n'
                '\tAlford\n'
                '\tBall\n'
                '\tHamilton\n'
                '\tHoliday\n'
                '\tWelsh\n')

    CURR_SERVER = SERVER_SETUP[CURR_SERVER_ID]
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [{server}] %(message)s'.format(server=CURR_SERVER_ID),
        filename='{server}.log'.format(server=CURR_SERVER_ID))

    main()


# References:
# https://developers.google.com/places/web-service/details
# https://www.w3.org/Protocols/rfc2616/rfc2616-sec9.html#sec9.3
# https://pymotw.com/3/asyncio/io_coroutine.html

