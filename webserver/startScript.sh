#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
export PATH=$SCRIPT_DIR:$PATH
export ENV=prod
umask 000
uvicorn main:app --host 0.0.0.0 --port 8080