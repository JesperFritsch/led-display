import json
import sys
import os
import asyncio
import firebase_admin
import random
import time
import argparse
from firebase_admin import credentials
from firebase_admin import db
from firebase_admin import storage
from concurrent.futures import ProcessPoolExecutor

# from rgbmatrix import RGBMatrix, RGBMatrixOptions
# from PIL import Image

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import common_config

cred = credentials.Certificate("/home/pi/led-matrix-tests/pixelart-dcaff-firebase-adminsdk-84hbl-285571f603.json")

DEFAULT_STORE_LOCATION = os.path.join(os.getcwd(), 'downloaded_images.data')
DISPLAY_TIME_MS = 200


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


class SocketHandler:
    def __init__(self, sock_file) -> None:
        self.sock_file = sock_file

    async def run_loop(self):
        reader, writer = await asyncio.open_unix_connection(self.sock_file)
        try:
            while True:
                data = await reader.readline()
                if data:
                    cmds = json.loads(data)
                    print(json.dumps(cmds, indent='  '))
                else:
                    print('Connection closed')
                    break

        except asyncio.CancelledError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

class DisplayHandler:
    def __init__(self) -> None:
        self.sleep_dur_ms = 100
        self.display_dur_ms = DISPLAY_TIME_MS
        self.current_image = None
        self.next_image = None
        self.switch_time = 0

    async def display_next_image(self):
        matrix.Clear()
        matrix.SetImage(self.next_image)
        self.switch_time = 0

    async def run_loop(self):
        try:
            self.next_image = image_handler.get_next_img()
            while True:
                if (time.time() / 1000) - self.switch_time  >= self.display_dur_ms:
                    await self.display_next_image()
                    self.next_image = await image_handler.get_next_img()
                await asyncio.sleep(self.sleep_dur_ms / 1000)
        except KeyboardInterrupt:
            print("shutting down")
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

    def add_image(self, image_name):
        self.images.append(image_name)

    def add_image_to_queue(self, image_name):
        self.image_queue.append(image_name)

    def remove_image(self, image_name):
        self.images.pop(image_name)

    async def scan_dir(self):
        while True:
            asyncio.sleep(1 / self.scan_frequency)
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

    def get_next_image_path(self):
        if self.image_queue:
            img_name = self.image_queue.pop(0)
        else:
            img_name = self.images[self.nr_slides % len(self.images)]
            self.nr_slides += 1
        return os.path.join(self.image_dir, img_name)

    async def get_image_obj(self, image_path):
        image = Image.open(image_path)
        image.thumbnail((self.width, self.height), Image.ANTIALIAS)
        return image.convert('RGB')

    async def get_next_img(self):
        img_path = self.get_next_image_path()
        with ProcessPoolExecutor() as pool:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                pool,
                self.get_image_obj(img_path)
            )
        return result


def get_matrix():
    options = RGBMatrixOptions()
    options.rows = 64
    options.cols = 64
    options.brightness = 40
    options.gpio_slowdown = 0
    options.chain_length = 1
    options.parallel = 1
    options.hardware_mapping = 'regular'  # If you have an Adafruit HAT: 'adafruit-hat'
    return RGBMatrix(options = options)

def get_unfetched_images(available_images, image_handler):
    local_images = image_handler.store.get_entries()
    missing_images = [img for img in available_images if img not in local_images]
    for img in missing_images:
        img_local_name = image_handler.download_image(img)
        image_handler.add_image_to_queue(img_local_name)
        image_handler.add_image(img_local_name)


async def main():
    socket_loop_task = asyncio.create_task(socket_handler.run_loop())
    display_loop_task = asyncio.create_task(display_handler.run_loop())
    scan_dir_task = asyncio.create_task(image_handler.scan_dir())
    await asyncio.gather(
        socket_loop_task,
        display_loop_task,
        scan_dir_task
        )

async def handleNewImage(event):
    if isinstance(event.data, str):
        img_path = event.data
        img_local_name = await asyncio.to_thread(image_handler.download_image(img_path))
        image_handler.add_image_to_queue(img_local_name)
        image_handler.add_image(img_local_name)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--image_dir", help="Path to a directory of images", required=True)
    args = ap.parse_args(sys.argv[:1])
    matrix = get_matrix()
    image_handler = ImageHandler(args.image_dir, matrix.width, matrix.height)
    display_handler = DisplayHandler()
    socket_handler = SocketHandler(common_config.SOCKET_FILE)
    store = StoreFileHander(DEFAULT_STORE_LOCATION)
    ref = db.reference('/led_display/')
    slideshow_ref = ref.child("img_slideshow")
    available_images = list(slideshow_ref.get().values())
    get_unfetched_images(available_images, image_handler)
    listener = slideshow_ref.listen(handleNewImage)

    asyncio.run(main())