#!/bin/bash
export PATH=/home/pi/led-display/driver:$PATH
umask 000
sudo python3 /home/pi/led-display/driver/driver.py -i /home/pi/led-display/driver/images
