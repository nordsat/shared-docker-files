#!/bin/bash

eval "$(micromamba shell hook --shell bash)"
micromamba activate

/opt/conda/bin/trollstalker.py -c /config/trollstalker.ini -C ${READER}