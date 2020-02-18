# Use the DOCKER HUB to download the chromiums and then push back to git

FROM python:latest
MAINTAINER Ken Wang <463407426@qq.com>
ENV LANG C.UTF-8
ENV REFRESHED_AT 2019-10-20

# Variables & Environments
ARG GIT_TOKEN=0
ARG GIT_REPO=https://${GIT_TOKEN}@github.com/Bugazelle/chromium-all-old-stable-versions.git
ARG GIT_NAME=Bugazelle
ARG GIT_EMAIL=zi_cheng@qq.com
ARG GIT_BRANCH=master
ARG FORCE_CRAWL=false
ENV HOME=/home/chromium

# Copy src to docker
COPY ./src/ $HOME/src
COPY ./chromium.stable.json $HOME
COPY ./chromium.stable.csv $HOME

# Set working directory
WORKDIR $HOME

# Run: Install basic components
RUN chmod -R +x $HOME/src && \
    ls -l $HOME/src && \
    $HOME/src/base.sh

# Run: Download chromiums
RUN $HOME/src/chromium.sh

# Run: Push back to git
RUN $HOME/src/git.sh
