#!/usr/bin/env bash

set -xe

apt-get update
apt-get -y install git zip unzip wget curl
curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | bash
pip install -r $HOME/src/requirements.txt
