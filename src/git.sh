#!/usr/bin/env bash

set -xe

# Clone git repo
git clone --branch master $GIT_REPO

# Config git repo
repo_name_with_postfix="${GIT_REPO##*/}"
repo_postfix=".git"
repo_name="${repo_name_with_postfix/$repo_postfix/}"
cd $repo_name
git config user.name "$GIT_NAME"
git config user.email "$GIT_EMAIL"

# Push
git checkout master
git fetch origin
git pull
cp -a $HOME/*.json repo_name/src
mv $HOME/repo_name/src/chromium.json $HOME/repo_name/
cp -a $HOME/chromium.csv repo_name/
cp -a $HOME/Downloads/. repo_name/
git lfs track "*.zip"
git add .gitattributes
git commit -m "[Auto] Track *.zip files using Git LFS"
git add .;
git commit -am "[Auto] Push Data From Docker Hub";
git push origin master;

# Clean
cd ..
rm -rf $repo_name
