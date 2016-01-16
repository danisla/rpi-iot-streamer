FROM python:3-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget libfreetype6 dbus libsmbclient libssh-4 \
    libpcre3 fonts-freefont-ttf fbset rtmpdump \
  && apt-get clean

RUN wget http://omxplayer.sconde.net/builds/omxplayer_0.3.6~git20150912~d99bd86_armhf.deb -O /tmp/omxplayer.deb

# armf only
#RUN dpkg -i /tmp/omxplayer.deb

RUN pip3 install \
    paho-mqtt livestreamer tornado pymongo docker-py

WORKDIR /opt
