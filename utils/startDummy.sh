#!/bin/bash
export PATH=/home/pi/led-display/driver:$PATH
umask 000
python3 /home/pi/led-display/utils/socket_dummy.py