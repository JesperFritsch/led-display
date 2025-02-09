import json
import sys
import os
import asyncio

from typing import Dict, Any
from fastapi import FastAPI
from fastapi import WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, HTMLResponse, FileResponse
from fastapi.exceptions import HTTPException
from starlette.types import Scope

from home_led_matrix.connection import ConnClient, Request

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from config import server_config

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


app = FastAPI()

app.mount("/static", NoCacheStaticFiles(directory='static'), name='static')
active_websockets = set()

ctl_client = ConnClient(host=server_config.prod_config['connHost'])

def update_handler(update: Dict[str, Any], active_websockets):
    async def send_to_all():
        for connection in active_websockets:
            await connection.send_json(update)
    asyncio.run(send_to_all())

ctl_client.set_update_handler(lambda update: update_handler(update, active_websockets))

driver_image_dir = None


@app.on_event('startup')
async def start_app():
    ctl_client.start_listening()

@app.on_event('shutdown')
async def shutdown_app():
    ctl_client.stop_listening()

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
        driver_image_dir = await ctl_client.get('image_dir')

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
            request = Request()
            for key in payload.get("get", []):
                request.get(key)
            for key, value in payload.get("set", {}).items():
                request.set(key, value)
            for action in payload.get("action", []):
                request.action(action)
            resp = ctl_client.request(request)
            if resp.errors:
                print("Errors: ", resp.errors)
            await websocket.send_json(resp.gets)

            # if resp.sets:
            #     for connection in active_websockets:
            #         #only echo the 'set' part of the message to all of the other clients
            #         await connection.send_json(resp.sets)
    except Exception as e:
        print("Websocket error: ", e)
    finally:
        active_websockets.remove(websocket)

