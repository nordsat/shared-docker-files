#!/usr/bin/bash

source /opt/conda/.bashrc
# source /config/env-variables

micromamba activate
/opt/conda/bin/trollstalker.py -v -c /config/trollstalker.ini
