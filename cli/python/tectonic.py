"""
python client for tectonic server
"""

import ffi
import socket
import json
import struct
import time
import sys
import asyncio
from io import StringIO
import pandas as pd
import numpy as np

class TectonicDB():
    """
    Example Usage:
        from tectonic import TectonicDB
        import json
        import asyncio

        async def subscribe(name):
            db = TectonicDB()
            print(await db.subscribe(name))
            while 1:
                _, item = await db.poll()
                if item == b"NONE":
                    await asyncio.sleep(0.01)
                else:
                    yield json.loads(item)

        class TickBatcher(object):
            def __init__(self, db_name):
                self.one_batch = []
                self.db_name = db_name

            async def batch(self):
                generator = subscribe(self.db_name)
                async for item in generator:
                    self.one_batch.append(item)

            async def timer(self):
                while 1:
                    await asyncio.sleep(5)
                    print(len(self.one_batch))


        if __name__ == '__main__':
            loop = asyncio.get_event_loop()
            proc = TickBatcher("bnc_xrp_btc")
            loop.create_task(proc.batch())
            loop.create_task(proc.timer())
            loop.run_forever()
            loop.close()
    """
    def __init__(self, host="localhost", port=9001):
        self.subscribed = False
        self.host = host
        self.port = port

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_address = (host, port)
        self.sock.connect(server_address)

    async def cmd(self, cmd):
        loop = asyncio.get_event_loop()
        if type(cmd) != str:
            message = (cmd.decode() + '\n').encode()
        else:
            message = (cmd+'\n').encode()
        loop.sock_sendall(self.sock, message)

        if "GET" in cmd and "JSON" not in cmd and "CSV" not in cmd:
            return await self._recv_dtf()
        else:
            return await self._recv_text()

    async def _recv_dtf(self):
        success, data = await self._recv_text()
        ups = ffi.parse_stream(data)
        return success, ups

    async def _recv_text(self):
        loop = asyncio.get_event_loop()
        header = await loop.sock_recv(self.sock, 9)
        current_len = len(header)
        while current_len < 9:
            header += await loop.sock_recv(self.sock, 9-current_len)
            current_len = len(header)

        success, bytes_to_read = struct.unpack('>?Q', header)
        if bytes_to_read == 0:
            return success, ""

        body = await loop.sock_recv(self.sock, 1)
        body_len = len(body)
        while body_len < bytes_to_read:
            len_to_read = bytes_to_read - body_len
            if len_to_read > 32:
                len_to_read = 32
            body += await loop.sock_recv(self.sock, len_to_read)
            body_len = len(body)
        return success, body

    def destroy(self):
        self.sock.close()

    async def info(self):
        return await self.cmd("INFO")

    async def countall(self):
        return await self.cmd("COUNT ALL")

    async def countall_in_mem(self):
        return await self.cmd("COUNT ALL IN MEM")

    async def ping(self):
        return await self.cmd("PING")

    async def help(self):
        return await self.cmd("HELP")

    async def insert(self, ts, seq, is_trade, is_bid, price, size, dbname):
        return await self.cmd("INSERT {}, {}, {} ,{}, {}, {}; INTO {}"
                        .format( ts, seq,
                            't' if is_trade else 'f',
                            't' if is_bid else 'f', price, size,
                            dbname))

    async def add(self, ts, seq, is_trade, is_bid, price, size):
        return await self.cmd("ADD {}, {}, {} ,{}, {}, {};"
                        .format( ts, seq,
                            't' if is_trade else 'f',
                            't' if is_bid else 'f', price, size))

    async def getall(self):
        success, ret = await self.cmd("GET ALL")
        return success, list(map(lambda x:x.to_dict(), ret))

    async def get(self, n):
        success, ret = await self.cmd("GET {}".format(n))
        if success:
            return success, list(map(lambda x:x.to_dict(), ret))
        else:
            return False, None

    async def clear(self):
        return await self.cmd("CLEAR")

    async def clearall(self):
        return await self.cmd("CLEAR ALL")

    async def flush(self):
        return await self.cmd("FLUSH")

    async def flushall(self):
        return await self.cmd("FLUSH ALL")

    async def create(self, dbname):
        return await self.cmd("CREATE {}".format(dbname))

    async def use(self, dbname):
        return await self.cmd("USE {}".format(dbname))

    async def unsubscribe(self):
        await self.cmd("UNSUBSCRIBE")
        self.subscribed = False

    async def subscribe(self, dbname):
        res = await self.cmd("SUBSCRIBE {}".format(dbname))
        if res[0]:
            self.subscribed = True
        return res

    async def poll(self):
        return await self.cmd("")

    async def range(self, dbname, start, finish):
        self.use(dbname)
        data = await self.cmd("GET ALL FROM {} TO {} AS CSV".format(start, finish).encode())
        data = data[1]
        return data
