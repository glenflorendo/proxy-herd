import asyncio

@asyncio.coroutine
def tcp_echo_client(message, loop):
    reader, writer = yield from asyncio.open_connection('localhost', 17630,
                                                        loop=loop)

    print('Send: %s' % message)
    writer.write(message.encode())

    data = yield from reader.read(10000)
    print('Received: %s' % data.decode())

    print('Close the socket')
    writer.close()

message = 'IAMAT kiwi.cs.ucla.edu +34.068930-118.445127 1479413884.392014450'
loop = asyncio.get_event_loop()
loop.run_until_complete(tcp_echo_client(message, loop))

message = 'WHATSAT kiwi.cs.ucla.edu 10 5'
loop = asyncio.get_event_loop()
loop.run_until_complete(tcp_echo_client(message, loop))


message = 'AT Alford +0.263873386 kiwi.cs.ucla.edu +34.068930-118.445127 1479413884.392014450'
loop = asyncio.get_event_loop()
loop.run_until_complete(tcp_echo_client(message, loop))
loop.close()