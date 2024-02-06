#!/usr/bin/bash

source /opt/conda/.bashrc
source /config/env-variables

micromamba activate
if [ -e /config/segment_gatherer.yaml ]; then
    /opt/conda/bin/segment_gatherer.py -v -c /config/segment_gatherer.yaml
else
    /opt/conda/bin/segment_gatherer.py -v -c /config/segment_gatherer.conf -C default
fi
