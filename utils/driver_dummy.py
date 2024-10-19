import json
import sys
import os
import argparse
import asyncio
import random
import time
import argparse
import logging
from pathlib import Path
# from rgbmatrix import RGBMatrix, RGBMatrixOptions
# from PIL import Image

log = logging.getLogger(Path(__file__).stem)

logging.basicConfig(level=logging.DEBUG)
logging.getLogger().setLevel(logging.DEBUG)

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import common_config as c_cfg
from config import driver_config as d_cfg
from driver.msg_interface import MsgHandler

async def main():
    global listener
    socket_loop_task = asyncio.create_task(msg_handler.socket_handler.run_loop())
    await asyncio.gather(
        socket_loop_task,
    )

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--image_dir", help="Path to a directory of images", required=True)
    args = ap.parse_args(sys.argv[1:])
    msg_handler = MsgHandler()

    def image_dir_resp():
        return args.image_dir

    def image_names():
        return [x for x in os.listdir(args.image_dir) if x.endswith('.png')]

    async def set_image_fake(img_name):
        print(f'setting image: {img_name}')

    def get_image():
        return 'some_image'

    async def fake_setter(value):
        print(f'setting: {value}')
        return

    def get_modes():
        return ['images', 'snakes']

    def default_handler(meth_type, key, value):
        log.debug(f"Default handler called with '{meth_type}', '{key}', '{value}'")

    msg_handler.default_handler = default_handler

    msg_handler.add_handlers('image_dir', getter=image_dir_resp)
    msg_handler.add_handlers('images', getter=image_names)
    msg_handler.add_handlers('image', getter=get_image, setter=set_image_fake)
    msg_handler.add_handlers('display_modes', getter=get_modes)
    msg_handler.add_handlers('display_mode', fake_setter, lambda: 'snakes')
    msg_handler.add_handlers('nr_snakes', fake_setter, lambda: 20)
    msg_handler.add_handlers('snake_maps', fake_setter, lambda: ['map1', 'map2'])
    msg_handler.add_handlers('snake_map', fake_setter, lambda: 'map1')

    listener = None

    asyncio.run(main())