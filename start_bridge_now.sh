#!/bin/bash
pkill -f bridge_server.py
sleep 2
cd /home/juan/AuroraIA/application
/home/juan/AuroraIA/application/.venv/bin/python bridge_server.py > /home/juan/AuroraIA/application/bridge.log 2>&1 &
echo "Started."
