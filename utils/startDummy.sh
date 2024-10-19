#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
export PATH=$SCRIPT_DIR:$PATH
umask 000
python3 $SCRIPT_DIR/driver_dummy.py -i $SCRIPT_DIR/../webserver/images