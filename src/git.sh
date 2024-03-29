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
git checkout $GIT_BRANCH
git fetch origin
git pull
cp -a $HOME/*.json $HOME/$repo_name/src
#mv $HOME/$repo_name/src/chromium.stable.json $HOME/$repo_name/
#cp -a $HOME/chromium.stable.csv $HOME/$repo_name/
cp -a $HOME/Downloads/. $HOME/$repo_name/ || true
# git lfs track "*.zip"
# git add .gitattributes
# git commit -m "[Auto] Track *.zip files using Git LFS"
git add .;
git commit -am "[Auto] Push Data From Docker Hub";
git push origin $GIT_BRANCH;

# Clean
cd ..
rm -rf $repo_name
