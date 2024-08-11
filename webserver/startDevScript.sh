#!/bin/bash
export PATH=/home/pi/led-display/webserver:$PATH
umask 000
uvicorn main:app --host 0.0.0.0 --port 8080 --reload

