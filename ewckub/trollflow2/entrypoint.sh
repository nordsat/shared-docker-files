#!/usr/bin/bash

source /opt/conda/.bashrc
source /config/env-variables

micromamba activate
/opt/conda/bin/satpy_launcher.py -n false -a ${MESSAGE_SOURCE} -c /config/trollflow2_log_config.yaml /config/trollflow2.yaml
