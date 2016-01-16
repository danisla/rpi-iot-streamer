# Raspberry Pi IoT Video Streaming Appliance

Docker image that will connect to the AWS IoT service and play streams when the shadow is update.

A REST api is also available to start/stop/restart the stream.

The stream is started in a separate container, the `iot-streamer.py` script starts the container. 
