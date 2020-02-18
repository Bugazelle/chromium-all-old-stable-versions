#!/usr/bin/env bash

set -xe

cp -a $HOME/src/*.json $HOME || true
# Python 2.7
python $HOME/src/chromium.py --force=$FORCE_CRAWL
