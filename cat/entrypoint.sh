#!/bin/bash
#source /opt/conda/.bashrc
source /config/env-variables
#eval "$(micromamba shell hook --shell bash)"
#micromamba activate
sleep 3
python /usr/local/bin/cat.py /config/cat_metop.cfg -v -c ${CAT_CONFIG_ITEM} #-v = verbose. -c = config item