import json
import sys
import os
import asyncio

from fastapi import FastAPI
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from fastapi.responses import HTMLResponse
from starlette.types import Scope

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from config import common_config

class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response: Response = await super().get_response(path, scope)
        no_cache_headers = {
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        response.headers.update(no_cache_headers)
        return response

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
                    print(json.loads(data))
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


app = FastAPI()

app.mount("/static", NoCacheStaticFiles(directory='static'), name='static')
active_sockets = set()

socket_server = SocketServer(common_config.SOCKET_FILE)

socket_server_task = None

@app.on_event('startup')
async def start_app():
    global socket_server_task
    socket_server_task = asyncio.create_task(socket_server.start())

@app.on_event('shutdown')
async def shutdown_app():
    global socket_server_task
    if socket_server_task:
        socket_server_task.cancel()
        try:
            await socket_server_task
        except asyncio.CancelledError:
            print("Socket server task cancelled.")
        finally:
            await socket_server.stop()

@app.get("/", response_class=HTMLResponse)
async def get():
    with open('static/index.html') as f:
        content = f.read()
    headers = {
        'Expires': 0,
        'Pragma': 'no-cache'
    }
    return HTMLResponse(content=content, headers=headers)

@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print(f"Connected client to websocket: {websocket.client}")
    active_sockets.add(websocket)
    try:
        while True:
            payload = await websocket.receive_json()
            await socket_server.send_message(payload)
            for connection in active_sockets:
                await connection.send_json(payload)
    except WebSocketDisconnect:
        active_sockets.remove(websocket)
    except:
        pass
