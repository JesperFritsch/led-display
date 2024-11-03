import json
import sys
import os
import asyncio
import firebase_admin
import websockets
import random
import time
import argparse
import struct
import logging
import aiohttp
from pathlib import Path
from collections import deque
from firebase_admin import credentials
from firebase_admin import db
from firebase_admin import storage
from concurrent.futures import ProcessPoolExecutor

from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image

log = logging.getLogger(Path(__file__).stem)
log.setLevel(logging.ERROR)
log_handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_handler.setFormatter(formatter)
log.addHandler(log_handler)


p = os.path.dirname(os.path.dirname(__file__))
print(f"Adding path: {p}")
sys.path.append(p)

from config import common_config as c_cfg
from config import driver_config as d_cfg
from msg_interface import MsgHandler
cred = credentials.Certificate(os.path.join(os.path.dirname(os.path.dirname(__file__)),"pixelart-dcaff-eefc1ed77b07.json"))

DEFAULT_STORE_LOCATION = os.path.join(os.getcwd(), 'downloaded_images.data')

app_config = {
    'databaseURL': 'https://pixelart-dcaff-default-rtdb.firebaseio.com',
    'storageBucket': 'pixelart-dcaff.appspot.com'
}

app = firebase_admin.initialize_app(cred, app_config)

class StoreFileHander:
    def __init__(self, filepath) -> None:
        self.filepath = filepath

    def get_entries(self):
        with open(self.filepath, 'a+') as file:
            file.seek(0)
            return [img.strip('\n') for img in file.readlines()]

    def set_entry(self, entry):
        with open(self.filepath, 'a+') as file:
            file.seek(0, 2)
            file.write(f"{entry}\n")


class SnakeHandler:
    def __init__(self) -> None:
        self.nr_snakes = 7
        self.food_count = 15
        self.calc_timeout = 2500
        self.food_decay = 300
        self.snakes = []
        self.fps = 10
        self.map = None
        self.available_maps = []
        self.last_step_time = 0
        self.pixel_changes_buf = deque()
        self.stream_task = None
        self.stream_done = False
        self.websocket = None
        self.remote_host_name = "homeserver" # stationary pc
        self.stream_protocol = "ws" # stationary pc
        self.stream_port = 42069
        self.target_buffer_size = 100
        self.min_request_size = 2
        self.pending_changes = 0

    async def set_map(self, value):
        try:
            self.map = value
        except Exception as e:
            log.error(e)

    async def set_food_decay(self, value):
        try:
            self.food_decay = int(value)
        except Exception as e:
            log.error(e)

    def get_food_decay(self):
        return self.food_decay

    async def set_calc_timeout(self, value):
        try:
            self.calc_timeout = int(value)
        except Exception as e:
            log.error(e)

    def get_calc_timeout(self):
        return self.calc_timeout

    def get_map(self):
        return self.map

    def get_maps(self):
        return self.available_maps

    async def fetch_available_maps(self):
        try:
            async with aiohttp.ClientSession() as session:
                params = {'conf': 'maps'}
                async with session.get(f'http://{self.remote_host_name}:{self.stream_port}/api/config_data', params=params) as resp:
                    resp_dict = await resp.json()
                    maps = resp_dict['maps']
                    self.available_maps = maps
        except Exception as e:
            log.error(e)
            self.available_maps = []

    def load_map(self, init_data):
        height = init_data['height']
        width = init_data['width']
        blocked_value = init_data['blocked_value']
        base_map = init_data['base_map']
        color_map = init_data['color_mapping']
        r, g, b = color_map[str(blocked_value)]
        neighbors = ((0, 1), (1, 0), (0, -1), (-1, 0))
        for y, row in enumerate(base_map):
            e_y = y * 2
            for x, pixel in enumerate(row):
                e_x = x * 2
                if pixel == blocked_value:
                    display_handler.matrix.SetPixel(e_x, e_y, r, g, b)
                    #fill in the gaps
                    try:
                        for dx, dy in neighbors:
                            if base_map[y + dy][x + dx] == blocked_value:
                                display_handler.matrix.SetPixel(e_x + dx, e_y + dy, r, g, b)
                    except Exception as e:
                        log.error(e)

    async def get_next_change(self):
        change = None
        changes_buf_len = len(self.pixel_changes_buf)
        # If we are not fetching data and the buffer is empty, start the stream
        if self.stream_task is None:
            self.stream_task = asyncio.create_task(self.start_snake_stream())

        if changes_buf_len == 0 and self.stream_done:
            await self.stop_snake_stream()

        if changes_buf_len < self.target_buffer_size:
            if self.websocket is not None:
                request_size = self.target_buffer_size - changes_buf_len - self.pending_changes
                try:
                    if request_size >= self.min_request_size:
                        self.pending_changes += request_size
                        await self.websocket.send(f'GET {request_size}')
                except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedOK):
                    log.debug('Connection closed')
        log.debug(f'Changes buffer len: {changes_buf_len}, pending changes: {self.pending_changes}')
        if changes_buf_len > 0:
            change = self.pixel_changes_buf.popleft()
        return change

    async def stop_snake_stream(self):
        log.debug("stopping stream")
        if self.websocket is not None:
            log.debug("closing websocket")
            try:
                await self.websocket.close()
            except Exception as e:
                log.error(e)
            self.websocket = None
        if self.stream_task is not None:
            self.stream_task.cancel()
        self.stream_task = None
        self.stream_done = False # reset the stream done flag
        self.pixel_changes_buf.clear()
        self.pending_changes = 0
        display_handler.matrix.Clear()


    async def start_snake_stream(self):
        self.stream_done = False
        log.debug('starting stream')
        self.pixel_changes_buf.clear()
        self.pending_changes = 0
        await self.fetch_available_maps()
        try:
            uri = f"{self.stream_protocol}://{self.remote_host_name}:{self.stream_port}/ws"
            log.debug(f'connecting to {uri}')
            self.websocket = await websockets.connect(uri)
            log.debug('connected to stream')
        except Exception as e:
            log.debug(f'could not connect to {uri}')
            log.error(e)
            return
        config = {
            "calc_timeout": self.calc_timeout,
            "food_decay": self.food_decay,
            "grid_width": 32,
            "grid_height": 32,
            "food": self.food_count,
            "food_decay": self.food_decay,
            "snake_count": self.nr_snakes,
            "data_mode": "pixel_data",
            "data_on_demand": True,
            "map": self.map
        }
        try:
            await self.websocket.send(json.dumps(config))
            ack = await self.websocket.recv() # get the ok from the server
            init_data = json.loads(await self.websocket.recv()) # get the initialization data
            self.load_map(init_data)
            while True:
                try:
                    data = await self.websocket.recv()
                    if data:
                        if data == 'END':
                            break
                        change = [((x, y), (r, g, b)) for x, y, r, g, b in struct.iter_unpack("BBBBB", data)]
                        self.pixel_changes_buf.append(change)
                        self.pending_changes -= 1
                    else:
                        break
                except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedOK):
                    break
                except Exception as e:
                    log.error(e)
                    break

        except asyncio.CancelledError:
            return
        finally:
            if self.websocket is not None:
                await self.websocket.close()
            self.websocket = None
            self.stream_done = True

    async def restart(self, value):
        log.debug("restarting snakes")
        await self.stop_snake_stream()

    async def set_fps(self, value):
        try:
            self.fps = int(value) or 1
        except Exception as e:
            log.error(e)

    def get_fps(self):
        return self.fps

    async def set_nr_snakes(self, value):
        try:
            self.nr_snakes = int(value)
        except Exception as e:
            log.error(e)

    def get_nr_snakes(self):
        return self.nr_snakes

    async def set_food_count(self, value):
        try:
            self.food_count = int(value)
        except Exception as e:
            log.error(e)

    def get_food_count(self):
        return self.food_count

    async def set_food_decay(self, value):
        try:
            self.food_decay = int(value)
        except Exception as e:
            log.error(e)

    def get_food_decay(self):
        return self.food_decay


class DisplayHandler:
    def __init__(self) -> None:
        self.sleep_dur_ms = 50
        self.display_dur_sec = 60
        self.current_image = None
        self.next_image = None
        self.switch_time = 0
        self.matrix = None
        self.mode = 'images'
        self.modes = ['images', 'snakes']
        self.display_is_on = True

    def init_matrix(self):
        if self.matrix is None:
            options = RGBMatrixOptions()
            options.rows = 64
            options.cols = 64
            options.brightness = 40
            options.gpio_slowdown = 0
            options.chain_length = 1
            options.parallel = 1
            options.hardware_mapping = 'regular'
            self.matrix = RGBMatrix(options = options)

    def set_pixels(self, pixels):
        for (x, y), color in pixels:
            self.matrix.SetPixel(x, y, *color)

    async def refresh(self):
        self.matrix.Clear()
        self.matrix.SetImage(self.current_image, unsafe=False)

    async def set_mode(self, value):
        if value == 'snakes':
            self.matrix.Clear()
        if value == 'images':
            await snake_handler.stop_snake_stream()
            self.switch_time = 0
        self.mode = value

    def get_mode(self):
        return self.mode

    def get_modes(self):
        return self.modes

    async def set_image(self, image):
        self.next_image = image
        await self.display_next_image()

    async def display_next_image(self):
        self.matrix.Clear()
        self.matrix.SetImage(self.next_image, unsafe=False)
        self.current_image = self.next_image
        self.switch_time = time.time() * 1000
        await msg_handler.send_update('image')
        self.next_image = await image_handler.get_next_img()

    async def set_display_on(self, value):
        try:
            value = bool(value)
        except Exception as e:
            log.error(e)
        if value is False:
            self.matrix.Clear()
            self.display_is_on = False
            await snake_handler.stop_snake_stream()
        else:
            self.display_is_on = True
            self.switch_time = 0

    def get_display_on(self):
        return self.display_is_on

    async def set_brightness(self, value):
        try:
            self.matrix.brightness = int(value)
        except Exception as e:
            log.error(e)
        if self.mode == 'images':
            await self.refresh()

    def get_brightness(self):
        return self.matrix.brightness

    async def set_display_dur(self, value):
        try:
            self.display_dur_sec = int(value)
        except Exception as e:
            log.error(e)

    def get_display_dur(self):
        return self.display_dur_sec

    async def run_loop(self):
        try:
            self.next_image = await image_handler.get_next_img()
            while True:
                if self.display_is_on:
                    if self.mode == 'images':
                        if (time.time() * 1000) - self.switch_time  >= (self.display_dur_sec * 1000):
                            await self.display_next_image()
                    elif self.mode == 'snakes':
                        if (time.time()) >= (1 / snake_handler.fps + snake_handler.last_step_time):
                            snake_handler.last_step_time = time.time()
                            if change := await snake_handler.get_next_change():
                                self.set_pixels(change)
                await asyncio.sleep(self.sleep_dur_ms / 1000)
        except KeyboardInterrupt:
            log.info("shutting down")
            global listener
            listener.close()
            sys.exit(0)


class ImageHandler:
    def __init__(self, image_dir, width, height) -> None:
        self.images = os.listdir(image_dir)
        self.image_queue = []
        self.image_dir = image_dir
        self.width = width
        self.height = height
        self.newImages = []
        self.nr_slides = 0
        self.scan_frequency = 5
        self.current_img_name = None

    def get_image_names(self):
        return self.images

    def get_image_dir(self):
        return self.image_dir

    def add_image(self, image_name):
        self.images.append(image_name)

    def add_image_to_queue(self, image_name):
        self.image_queue.append(image_name)

    def remove_image(self, image_name):
        self.images.pop(image_name)

    async def scan_dir(self):
        while True:
            await asyncio.sleep(1 / self.scan_frequency)
            new_image_paths = list(filter(lambda x: x not in self.images, os.listdir(self.image_dir)))
            self.image_queue.extend(new_image_paths)
            self.images.extend(new_image_paths)

    def download_image(self, storage_path):
        #downloads an image and return the name of the resulting file.
        img_local_name = storage_path.replace('/', '-') + '.png'
        local_path = os.path.join(self.image_dir, img_local_name)
        # Create a reference to the storage
        bucket = storage.bucket()
        # Create a blob object
        blob = bucket.blob(storage_path)
        blob.download_to_filename(local_path)
        store.set_entry(storage_path)
        return img_local_name

    def get_image_obj(self, image_path):
        image = Image.open(image_path)
        image.thumbnail((self.width, self.height), Image.ANTIALIAS)
        return image.convert('RGB')

    async def proccess_img(self, img_name):
        img_path = os.path.join(self.image_dir, img_name)
        with ProcessPoolExecutor() as pool:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                pool,
                self.get_image_obj,
                img_path
            )
        return result

    async def get_next_img(self):
        try:
            img_name = self.image_queue.pop(0)
        except IndexError:
            img_name = self.images[self.nr_slides % len(self.images)]
            self.nr_slides += 1
        self.current_img_name = img_name
        return await self.proccess_img(img_name)

def get_unfetched_images(available_images, image_handler):
    local_images = store.get_entries()
    missing_images = [img for img in available_images if img not in local_images]
    for img in missing_images:
        img_local_name = image_handler.download_image(img)
        image_handler.add_image_to_queue(img_local_name)
        image_handler.add_image(img_local_name)

async def main():
    global listener
    await snake_handler.fetch_available_maps()
    new_image_queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    ref = db.reference('/led_display/')
    slideshow_ref = ref.child("img_slideshow")
    available_images = list(slideshow_ref.get().values())
    get_unfetched_images(available_images, image_handler)
    socket_loop_task = asyncio.create_task(msg_handler.socket_handler.run_loop())
    display_loop_task = asyncio.create_task(display_handler.run_loop())
    scan_dir_task = asyncio.create_task(image_handler.scan_dir())
    handleNewImage_task = asyncio.create_task(handleNewImage(new_image_queue))
    listener = slideshow_ref.listen(lambda event: newImageEvent(loop, new_image_queue, event))
    try:
        await asyncio.gather(
            socket_loop_task,
            display_loop_task,
            scan_dir_task,
            handleNewImage_task
        )
    except Exception as e:
        log.error(f"Error in main: {e}")
        log.debug("TRACE", exc_info=True)
        listener.close()

async def handleNewImage(new_image_queue):
    while True:
        img_path = await new_image_queue.get()
        img_local_name = await asyncio.to_thread(image_handler.download_image, img_path)
        image_handler.add_image_to_queue(img_local_name)
        image_handler.add_image(img_local_name)
        display_handler.next_image = await image_handler.get_next_img()
        await display_handler.display_next_image()
        new_image_queue.task_done()

def get_image():
    return image_handler.current_img_name

async def set_image(img_name):
    if display_handler.mode == 'images':
        img_obj = await image_handler.proccess_img(img_name)
        await display_handler.set_image(img_obj)

def newImageEvent(loop, new_image_queue, event):
    if isinstance(event.data, str):
        img_path = event.data
        asyncio.run_coroutine_threadsafe(new_image_queue.put(img_path), loop)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--image_dir", help="Path to a directory of images", required=True)
    args = ap.parse_args(sys.argv[1:])
    msg_handler = MsgHandler()
    display_handler = DisplayHandler()
    display_handler.init_matrix()
    image_handler = ImageHandler(args.image_dir, display_handler.matrix.width, display_handler.matrix.height)
    snake_handler = SnakeHandler()
    store = StoreFileHander(DEFAULT_STORE_LOCATION)

    msg_handler.add_handlers('brightness', display_handler.set_brightness, display_handler.get_brightness)
    msg_handler.add_handlers('display_dur', display_handler.set_display_dur, display_handler.get_display_dur)
    msg_handler.add_handlers('display_on', display_handler.set_display_on, display_handler.get_display_on)
    msg_handler.add_handlers('display_mode', display_handler.set_mode, display_handler.get_mode)
    msg_handler.add_handlers('display_modes', getter=display_handler.get_modes)
    msg_handler.add_handlers('image', set_image, get_image)
    msg_handler.add_handlers('image_dir', getter=image_handler.get_image_dir)
    msg_handler.add_handlers('images', getter=image_handler.get_image_names)
    msg_handler.add_handlers('nr_snakes', snake_handler.set_nr_snakes, snake_handler.get_nr_snakes)
    msg_handler.add_handlers('food', snake_handler.set_food_count, snake_handler.get_food_count)
    msg_handler.add_handlers('food_decay', snake_handler.set_food_decay, snake_handler.get_food_decay)
    msg_handler.add_handlers('snakes_fps', snake_handler.set_fps, snake_handler.get_fps)
    msg_handler.add_handlers('snake_map', snake_handler.set_map, snake_handler.get_map)
    msg_handler.add_handlers('snake_maps', getter=snake_handler.get_maps)
    msg_handler.add_handlers('restart_snakes', setter=snake_handler.restart)
    msg_handler.add_handlers('calc_timeout', snake_handler.set_calc_timeout, snake_handler.get_calc_timeout)
    msg_handler.add_handlers('food_decay', snake_handler.set_food_decay, snake_handler.get_food_decay)


    listener = None

    asyncio.run(main())
