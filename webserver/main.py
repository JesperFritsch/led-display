import json
import sys
import os
import asyncio

from fastapi import FastAPI
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, HTMLResponse, FileResponse, JSONResponse
from fastapi.exceptions import HTTPException
from starlette.types import Scope

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from config import common_config, server_config

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
        self.open_requests_futures = {}

    async def clientListener(self, reader, writer):
        try:
            while True:
                data = await reader.readline()
                if data:
                    json_data = json.loads(data)
                    #if there is a get request sent, then there might be events we are listening to for the response
                    if self.open_requests_futures.keys():
                        await self.future_setter(json_data)
                    for connection in active_websockets:
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

    async def future_setter(self, msgs_rec: dict):
        # Set events for recieved messages if there are any
        for parameter, value in msgs_rec.items():
            if parameter in self.open_requests_futures.keys():
                self.open_requests_futures[parameter].set_result(value)
                del self.open_requests_futures[parameter]

    async def clientWriter(self, data: dict):
        for reader, writer in self.connections:
            writer.write(data)
            await writer.drain()

    async def handleClient(self, reader, writer):
        self.connections.add((reader, writer))
        await self.clientListener(reader, writer)

    async def get_message_wait(self, parameter, value=None):
        # Send a message and return a future that will resolve when the first response of this message domes from the socket client
        if self.connections:
            msg = {'get': {parameter: value}}
            future = asyncio.Future()
            self.open_requests_futures[parameter] = future
            await self.send_message(msg)
            return await future

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
active_websockets = set()

socket_server = SocketServer(common_config.SOCKET_FILE)
socket_server_task = None

driver_image_dir = None


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

@app.get("/config.json")
async def get_config():
    if os.getenv('ENV') == 'prod':
        return server_config.prod_config
    elif os.getenv('ENV') == 'dev':
        return server_config.dev_config

@app.get("/", response_class=HTMLResponse)
async def get():
    with open('static/index.html') as f:
        content = f.read()
    headers = {
        'Expires': '0',
        'Pragma': 'no-cache'
    }
    return HTMLResponse(content=content, headers=headers)

@app.get("/images/{image_path:path}", response_class=FileResponse)
async def get_images(image_path: str):
    global driver_image_dir
    if driver_image_dir is None:
        driver_image_dir = await socket_server.get_message_wait('image_dir')

    file_path = os.path.join(driver_image_dir, image_path)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image not found.")

    return FileResponse(file_path)

@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print(f"Connected client to websocket: {websocket.client}")
    active_websockets.add(websocket)
    try:
        while True:
            payload = await websocket.receive_json()
            await socket_server.send_message(payload)
            for connection in active_websockets:
                #only echo the 'set' part of the message to all of the other clients
                await connection.send_json(payload.get('set'))
    except Exception as e:
        print("Websocket error: ", e)
    finally:
        active_websockets.remove(websocket)

