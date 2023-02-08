#!/usr/bin/bash

source /opt/conda/.bashrc
source /config/env-variables

micromamba activate
/opt/conda/bin/move_it_client.py -v /config/trollmoves_client.ini
