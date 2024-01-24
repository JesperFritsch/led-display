import json
import sys
import os
import asyncio
import firebase_admin
import random
import time
import argparse


sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import common_config as c_cfg
from config import driver_config as d_cfg

active_sockets = set()

class SocketServer:
    def __init__(self, path) -> None:
        self.path = path
        self.connections = set()
        self.server = None

    async def clientListener(self, reader, writer):
        try:
            while True:
                data = await reader.readline()
                if data:
                    json_data = json.loads(data)
                    for connection in active_sockets:
                        await connection.send_json(json_data)
                else:
                    print('Connection closed: ', writer.get_extra_info("peername"))
                    break
        except asyncio.CancelledError:
            pass
        finally:
            self.connections.discard((reader, writer))
            writer.close()
            await writer.wait_closed()

    async def clientWriter(self, data):
        for reader, writer in self.connections:
            writer.write(data)
            await writer.drain()

    async def handleClient(self, reader, writer):
        self.connections.add((reader, writer))
        await self.clientListener(reader, writer)

    async def handle_input(self):
        while True:
            msg_value = input('message: ')
            try:
                msg, value = msg_value.split(' ')
            except:
                continue
            payload = {msg: value}
            await self.send_message(payload)


    async def send_message(self, payload):
        jsonString = json.dumps(payload) + '\n'
        data = jsonString.encode('utf-8')
        await self.clientWriter(data)

    async def start(self):
        self.server = await asyncio.start_unix_server(self.handleClient, self.path)
        async with self.server:
            await self.server.serve_forever()

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        conn_copy = set(self.connections)
        for reader, writer in conn_copy:
            writer.close()
            await writer.wait_closed()
        self.connections.clear()
        if os.path.exists(self.path):
            os.remove(self.path)


class SocketClient:
    def __init__(self, sock_file) -> None:
        self.sock_file = sock_file

    async def start(self):
        while True:
            try:
                print(f"Trying to connect to socket: '{self.sock_file}'")
                reader, writer = await asyncio.open_unix_connection(self.sock_file)
                print(f"Connected to socket: {self.sock_file}")
            except ConnectionRefusedError as e:
                print(f"Socket not available: {e}")
                await asyncio.sleep(20)
            except Exception as e:
                print(f"Error connecting: {e}")
                await asyncio.sleep(10)
            else:
                try:
                    while True:
                        data = await reader.readline()
                        if data:
                            try:
                                msg = json.loads(data)
                                print(msg)
                            except Exception as e:
                                print(e)
                        else:
                            print('Connection closed')
                            break

                except asyncio.CancelledError:
                    pass
                finally:
                    writer.close()
                    await writer.wait_closed()

async def main():
    socket_client = SocketClient(c_cfg.SOCKET_FILE)
    socket_server = SocketServer(c_cfg.SOCKET_FILE)
    input_task = asyncio.create_task(socket_server.handle_input())
    client_task = asyncio.create_task(socket_client.start())
    server_task = asyncio.create_task(socket_server.start())
    await asyncio.gather([input_task, client_task, server_task])


if __name__ == '__main__':
    asyncio.run(main())