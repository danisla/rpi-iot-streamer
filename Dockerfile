FROM sena/rpi-python3:3.4.2

WORKDIR /usr/src/app

ENTRYPOINT python3 iot-streamer.py

RUN pip3 install \
    paho-mqtt livestreamer tornado docker-py pymongo

ADD iot-streamer.py .
