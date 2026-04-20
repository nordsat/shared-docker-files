#!/bin/bash

eval "$(micromamba shell hook --shell bash)"
micromamba activate
/opt/conda/bin/python /opt/conda/bin/segment_gatherer.py -c /config/segment_gatherer.yaml -v -l /logs/segment_gatherer_seviri_hrit.log