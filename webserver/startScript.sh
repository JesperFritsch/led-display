#!/bin/bash
source /home/matrix/projects/venvs/matrix_venv/bin/activate
export ENV=prod
umask 000
uvicorn main:app --host 0.0.0.0 --port 8080
