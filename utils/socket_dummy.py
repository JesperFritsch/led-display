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

class SocketHandler:
    def __init__(self, sock_file) -> None:
        self.sock_file = sock_file

    async def run_loop(self):
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


if __name__ == '__main__':
    socket_handler = SocketHandler(c_cfg.SOCKET_FILE)
    asyncio.run(socket_handler.run_loop())