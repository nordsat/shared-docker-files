#!/bin/bash

source /opt/nwcgeo_v2025.2_env.sh

/opt/bin/SAFNWCTM 2>&1 | tee -a /opt/logs/nohup.out

# SAFNWCTM command is started to the background, so wait for 10 years
# so the container doesn't exit immediately
sleep 315360000