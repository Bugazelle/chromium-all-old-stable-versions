#!/usr/bin/env bash

set -xe

cp -a $HOME/src/*.json $HOME || true
python $HOME/src/chromium.py
