#!/usr/bin/bash

source /opt/conda/.bashrc
source /config/env-variables

micromamba activate
/opt/conda/bin/segment_gatherer.py -v -c /config/segment_gatherer.conf -C default
