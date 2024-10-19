#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
export PATH=$SCRIPT_DIR:$PATH
umask 000
sudo python3 $SCRIPT_DIR/driver.py -i $SCRIPT_DIR/images