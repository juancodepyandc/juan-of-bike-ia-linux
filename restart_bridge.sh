#!/bin/bash
pkill -f bridge_server.py
sleep 3
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$DIR/application"
nohup "$DIR/application/.venv/bin/python" bridge_server.py > bridge.log 2>&1 &
disown
