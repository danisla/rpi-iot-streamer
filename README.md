# Raspberry Pi IoT Video Streaming Appliance

Docker image that will connect to the AWS IoT service and play streams when the shadow is update.

A REST api is also available to start/stop/restart the stream.

The stream is started in a separate container, the `iot-streamer.py` script starts the container.

## IoT Thing

Use the provided [`./make_thing.sh`] script to generate the certs and create the new thing in the Iot thing registry.

## API

Use the provide API Gateway definition and lambda functions to connect the API to the IoT service and control your Iot Streamer things.

 - API Gateway: [`./apigateway`](./apigateway)
 - Lambda functions: [`./lambda`](./lambda)
