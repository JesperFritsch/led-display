import os
import time
from snake_sim.render import core as render_core
from rgbmatrix import RGBMatrix, RGBMatrixOptions

runs_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'runs')



if __name__ == '__main__':
    options = RGBMatrixOptions()
    options.rows = 64
    options.cols = 64
    options.brightness = 40
    options.gpio_slowdown = 0
    options.chain_length = 1
    options.parallel = 1
    options.hardware_mapping = 'regular'
    matrix = RGBMatrix(options = options)
    latest_file = max([os.path.join(runs_dir, f) for f in os.listdir(runs_dir)], key=os.path.getctime)
    pixel_changes = render_core.pixel_changes_from_runfile(latest_file)
    framerate = 10
    changes = pixel_changes['changes']
    for step_data in changes:
        for (x, y), color in step_data:
            matrix.SetPixel(x, y, *color)
        time.sleep(1/framerate)