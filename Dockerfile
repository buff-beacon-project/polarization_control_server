# FROM ubuntu:18.04
FROM python:3.9
ENV DEBIAN_FRONTEND=noninteractive 
RUN apt-get update && \
     apt-get install -y \
     python3 \
     python3-dev \
     python3-pip \
     python3-pandas \
     python3-scipy \
     libtool pkg-config build-essential autoconf automake \
     libzmq3-dev \
     libftdi1 \
     git \ 
     && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /app/requirements.txt
WORKDIR /app
RUN python3 -m pip install --upgrade pip && \
     pip3 --no-cache-dir install -r requirements.txt
# Run pip3 --no-cache-dir install git+https://github.com/kshalm/bellanalysishelper
