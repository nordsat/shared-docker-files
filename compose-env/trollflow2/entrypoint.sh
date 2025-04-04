#!/bin/bash

eval "$(micromamba shell hook --shell bash)"
micromamba activate
/opt/conda/bin/satpy_launcher.py -n false -a ${MESSAGE_SOURCE} /config/${CONFIGFILE}
