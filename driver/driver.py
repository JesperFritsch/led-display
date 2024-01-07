import json
import sys
import os
import asyncio
import firebase_admin
import random
import argparse
from firebase_admin import credentials
from firebase_admin import db
from firebase_admin import storage

from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import common_config

cred = credentials.Certificate("/home/pi/led-matrix-tests/pixelart-dcaff-firebase-adminsdk-84hbl-285571f603.json")

DEFAULT_STORE_LOCATION = os.path.join(os.getcwd(), 'downloaded_images.data')
DISPLAY_TIME = 20
passed_time = DISPLAY_TIME

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

class ImageHandler:
    def __init__(self, image_dir, width, height) -> None:
        self.images = os.listdir(image_dir)
        self.image_queue = []
        self.image_dir = image_dir
        self.width = width
        self.height = height
        self.newImages = []
        self.store = StoreFileHander(DEFAULT_STORE_LOCATION)
        self.nr_slides = 0

    def add_image(self, image_name):
        self.images.append(image_name)

    def add_image_to_queue(self, image_name):
        self.image_queue.append(image_name)

    def remove_image(self, image_name):
        self.images.pop(image_name)

    def scan_dir(self):
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
        self.store.set_entry(storage_path)
        return img_local_name

    def get_next_img(self):
        if self.image_queue:
            img_name = self.image_queue.pop(0)
        else:
            img_name = self.images[self.nr_slides % len(self.images)]
            self.nr_slides += 1
        print(os.path.join(self.image_dir, img_name))
        image = Image.open(os.path.join(self.image_dir, img_name))
        image.thumbnail((self.width, self.height), Image.ANTIALIAS)
        return image.convert('RGB')

# Configuration for the matrix

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


def get_unfetched_images(available_images, imageHandler):
    local_images = imageHandler.store.get_entries()
    missing_images = [img for img in available_images if img not in local_images]
    for img in missing_images:
        img_local_name = imageHandler.download_image(img)
        imageHandler.add_image_to_queue(img_local_name)
        imageHandler.add_image(img_local_name)

def run(args):
    ref = db.reference('/led_display/')
    slideshow_ref = ref.child("img_slideshow")
    matrix = get_matrix()
    imageHandler = ImageHandler(args.image_dir, matrix.width, matrix.height)

    available_images = list(slideshow_ref.get().values())
    get_unfetched_images(available_images, imageHandler)
    def handleNewImage(event):
        if isinstance(event.data, str):
            img_path = event.data
            img_local_name = imageHandler.download_image(img_path)
            imageHandler.add_image_to_queue(img_local_name)
            imageHandler.add_image(img_local_name)
            global passed_time
            passed_time = DISPLAY_TIME
    listener = slideshow_ref.listen(handleNewImage)
    sleep_time = 0.1
    try:
        global passed_time
        passed_time = DISPLAY_TIME
        next_image = imageHandler.get_next_img()
        while True:
            if passed_time >= DISPLAY_TIME:
                next_image = imageHandler.get_next_img()
                matrix.Clear()
                matrix.SetImage(next_image)
                passed_time = 0
                imageHandler.scan_dir()
            passed_time += sleep_time
            time.sleep(sleep_time)
    except KeyboardInterrupt:
        print("shutting down")
        listener.close()
        sys.exit(0)

# Make image fit our screen.

async def connect_to_server():
    reader, writer = await asyncio.open_unix_connection(common_config.SOCKET_FILE)
    try:
        while True:
            data = await reader.readline()
            if data:
                cmds = json.loads(data)
                print(json.dumps(cmds, indent='  '))
            else:
                print('Connectino closed')
                break

    except asyncio.CancelledError:
        pass
    finally:
        writer.close()
        await writer.wait_closed()

def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--image_dir", help="Path to a directory of images", required=True)
    args = ap.parse_args(argv)
    run(args)
    asyncio.run(connect_to_server())

if __name__ == '__main__':
    main(sys.argv[:1])