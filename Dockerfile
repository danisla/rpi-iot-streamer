FROM sena/rpi-python3:3.4.2

#RUN apt-get update && apt-get install -y --no-install-recommends \
#    wget libfreetype6 dbus libsmbclient libssh-4 \
#    libpcre3 fonts-freefont-ttf fbset rtmpdump \
# && apt-get clean

#RUN wget http://omxplayer.sconde.net/builds/omxplayer_0.3.6~git20150912~d99bd86_armhf.deb -O /tmp/omxplayer.deb

#RUN dpkg -i /tmp/omxplayer.deb

RUN pip3 install \
    paho-mqtt livestreamer tornado docker-py pymongo

WORKDIR /opt

ADD iot-streamer.py .

ENTRYPOINT python3 iot-streamer.py
