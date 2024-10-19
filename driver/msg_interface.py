
import logging
import asyncio
import sys
import os
import json
import weakref
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from utils.useful_stuff import DotDict
from config import common_config
log = logging.getLogger(Path(__file__).stem)

class MsgHandler:
    def __init__(self) -> None:
        self.set_handlers = DotDict()
        self.get_handlers = DotDict()
        self.socket_handler = SocketHandler(common_config.SOCKET_FILE, self)
        self.default_handler = None

    def add_handlers(self, message_key, setter=None, getter=None):
        if setter is not None: self.set_handlers[message_key] = setter
        if getter is not None: self.get_handlers[message_key] = getter

    async def send_update(self, *msg_keys):
        message = {key: self.get_handlers[key]() for key in msg_keys}
        for key in msg_keys:
            try:
                val = self.get_handlers[key]()
            except KeyError:
                if self.default_handler is not None:
                    val = self.default_handler('send_update', key, None)
                val = None
                log.debug(f'Invalid message: "{key}"')
            message[key] = val
        await self.socket_handler.send_message(message)

    async def handle_msg(self, payload):
        tasks = []
        message = None
        for meth_type, msgs in payload.items():
            if meth_type == 'set':
                for key, value in msgs.items():
                    try:
                        tasks.append(asyncio.create_task(self.set_handlers[key](value)))
                    except KeyError:
                        if self.default_handler is not None:
                            self.default_handler(meth_type, key, value)
                        else:
                            log.debug(f'Invalid message: "{key}"')
                await asyncio.gather(*tasks)
            elif meth_type == 'get':
                if 'all' in msgs.keys():
                    message = {key: getter() for key, getter in self.get_handlers.items()}
                else:
                    message = {}
                    for get_key, val in msgs.items():
                        try:
                            get_value = self.get_handlers[get_key](val)
                        except TypeError:
                            get_value = self.get_handlers[get_key]()
                        except KeyError:
                            if self.default_handler is not None:
                                self.default_handler(meth_type, get_key, val)
                            else:
                                get_value = None
                                log.debug(f'Invalid message: "{key}"')
                    message[get_key] = get_value
        return message


class SocketHandler:
    def __init__(self, sock_file, msg_handler: MsgHandler) -> None:
        self.sock_file = sock_file
        self.connections = set()
        self.msg_handler: MsgHandler = weakref.ref(msg_handler)

    async def send_message(self, msg_dict):
        payload = json.dumps(msg_dict) + '\n'
        data = payload.encode('utf8')
        for r, w in self.connections:
            w.write(data)

    async def run_loop(self):
        while True:
            try:
                log.debug(f"Trying to connect to socket: '{self.sock_file}'")
                reader, writer = await asyncio.open_unix_connection(self.sock_file)
                self.connections.add((reader, writer))
                log.debug(f"Connected to socket: {self.sock_file}")
            except ConnectionRefusedError as e:
                log.error(f"Socket not available: {e}")
                await asyncio.sleep(20)
            except Exception as e:
                log.error(f"Error connecting: {e}")
                await asyncio.sleep(10)
            else:
                try:
                    while True:
                        data = await reader.readline()
                        if data:
                            try:
                                msg = json.loads(data)
                                log.debug(msg)
                                msg_handler = self.msg_handler()
                                response = await msg_handler.handle_msg(msg)
                                if response is not None:
                                    data_json = json.dumps(response) + '\n'
                                    data = data_json.encode('utf-8')
                                    writer.write(data)
                                    await writer.drain()
                            except Exception as e:
                                log.error('Some shit happened: ', e)
                                log.debug(response)
                        else:
                            log.debug('Connection closed')
                            break

                except asyncio.CancelledError as e:
                    log.error("Cancelled error")
                    log.error("TRACE", exc_info=True)

                finally:
                    writer.close()
                    await writer.wait_closed()
                    self.connections.remove((reader, writer))