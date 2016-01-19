import os
import sys
import random
from concurrent.futures import ThreadPoolExecutor
from tornado.concurrent import run_on_executor
from tornado import gen, ioloop, web, process
from tornado.options import define, options
import time
import signal
import docker
import re
import livestreamer
from livestreamer import NoPluginError, PluginError

from iot_streamer_rest import Application
from iot_streamer_thing import IotStreamerThing
from docker_lib import get_docker_client, find_containers

###################################
# Logging setup

import logging
logger = logging.getLogger(__file__)

###################################

# Program options.
define("debug", default=os.environ.get("DEBUG","false").lower() == "true", help="Enable debugging")
define("player_docker_image", default=os.environ.get("PLAYER_DOCKER_IMAGE","danisla/rpi-omxplayer:latest"), help="docker image tag for playing stream url")
define("rpi_player", default=os.environ.get("RPI_PLAYER","true").lower() == "true", type=bool, help="add additional docker args when starting player container to support RPI")
define("resolve_url", default=os.environ.get("RESOLVE_URL","true").lower() == "true", type=bool, help="use livestreamer to resolve streamable url")
define("grace_period", default=int(os.environ.get("GRACE_PERIOD", "10")), type=int, help="Player startup grace period before declaring error")

# Name of currently running container.
curr_container_name = '.*curr_stream.*'

thread_pool = ThreadPoolExecutor(max_workers=4)

################################################################################

@gen.coroutine
def create_stream_container(url, quality):
    cli = get_docker_client()

    container = None
    docker_image = None

    docker_image = options.player_docker_image

    if url.startswith("rtsp") or (options.rpi_player and url.startswith("rtmp")):
        # Just pass the url to the player, no checks.
        pass

    else:
        # Attempt to get streamable url via livestreamer
        streams = None
        try:
            streams = livestreamer.streams(url)
        except NoPluginError:
            return False, "Livestreamer is unable to handle the URL '{0}'".format(url)
        except PluginError as err:
            return False, "Plugin error: {0}".format(err)

        if not streams:
            return False, "No streams found on URL '{0}'".format(url)

        # Look for specified stream
        if quality not in streams:
            return False, "Unable to find '{0}' stream on URL '{1}'".format(quality, url)

        # We found the stream
        stream = streams[quality]

        if options.resolve_url:
            logger.info("Stream URL resolved to: '{0}'".format(stream.url))

            try:
                url = stream.url
            except Exception as e:
                return False, "Could not get url from stream, plugin class missing .url method: {0}".format(type(stream))

    container = None
    try:

        devices = []
        if options.rpi_player:
            for d in ["/dev/vchiq", "/dev/fb0", "/dev/snd"]:
                devices.append(d+":"+d+":rwm")

        volumes = []
        binds = []
        if options.rpi_player:
            for v in ["/opt/vc"]:
                binds.append(v+":"+v+":ro")
            volumes.append(v)


        host_config = cli.create_host_config(
            restart_policy={
                "MaximumRetryCount": 0,
                "Name": "always"
            },
            port_bindings={
                8000: 8000
            },
            devices=devices,
            binds=binds
        )

        if options.rpi_player:
            entrypoint = "omxplayer -b -o both"
        else:
            entrypoint = None

        container = cli.create_container(
            image=docker_image,
            entrypoint=entrypoint,
            command=url,
            ports=[8000],
            detach=True,
            name="curr_stream",
            volumes=volumes,
            host_config=host_config
        )
    except Exception as e:
        logger.error("Error creating docker container: {0}".format(e))
        #TODO: revert to previous stream on error

    if container:
        logger.info("Created container with image: '{0}'".format(docker_image))
        return container
    else:
        return None


def tail_logs(container_id):
    # Get container logs and send them to the logger.
    # This is blocking and should be run in a thread.
    cli = get_docker_client()
    for log in cli.attach(container_id, stream=True, stdout=True, stderr=True):
        logger.info(log)


@gen.coroutine
def start_container(container_id, grace_period=None):


    cli = get_docker_client()

    try:
        cli.start(container_id)
        thread_pool.submit(tail_logs, container_id)

    except Exception as e:
        logger.error("Could not start container {0}: {1}".format(container_id, e))
        return False

    if grace_period:

        # Verifies container is UP for at least the grace period time.
        count = 0
        while count < grace_period:
            count += 1
            time.sleep(1)

            active = yield is_stream_active()
            if not active:
                logger.warning("container failed to stay up for {0} seconds".format(grace_period))
                return False

            logger.info("Verifying container stays up, grace period remaining: '{0}'".format(options.grace_period - count))

        return True

    else:
        return True


@gen.coroutine
def start_stream(url, quality):

    container = yield create_stream_container(url, quality)

    if container:
        if container['Warnings']:
            logger.warning("Container created with warnings, ignoring: '{0}'".format(container['Warnings']))

        container_id = container["Id"]

        res = yield start_container(container_id, grace_period=options.grace_period)
        if res:
            options.curr_url = url
            options.curr_quality = quality

            return True, "Container started"
        else:
            return False, "Error starting stream container"
            #TODO: revert to previous stream on error

    else:
        return False, "Could not create docker container for url '{0}'".format(url)


@gen.coroutine
def is_stream_active():

    containers = find_containers(curr_container_name)
    running = []

    names_status = []
    for c in containers:
        names_status.append({
            "name": c["Names"],
            "status": c["Status"]
        })

        if c["Status"].startswith("Up"):
            running.append(c)

    return len(running) > 0


@gen.coroutine
def stop_stream():
    cli = get_docker_client()

    # Kill and remove existing containers.
    curr_containers = find_containers(curr_container_name, all=True)
    for c in curr_containers:
        i = c["Id"]
        if not c['Status'].startswith("Exited") and not c['Status'].startswith("Created"):
            logger.info("Killing container: '{0}'".format(c["Names"]))
            cli.kill(i)

        logger.info("Removing container: '{0}'".format(c["Names"]))
        cli.remove_container(i)

    options.curr_url = ''
    options.curr_quality = ''


################################################################################

if __name__ == "__main__":

    options.parse_command_line()

    logger.setLevel(logging.DEBUG if options.debug else logging.INFO)

    define("curr_url", default='', help="Current URL being displayed")
    define("curr_quality", default='', help="Current stream quality being displayed")

    define("mqtt_connected", default=False, help="Indicator that mqtt connect was successful")
    define("mqtt_subscribed", default=False, help="Indicator that mqtt subscribe was successful")

    define("start_stream", default=start_stream, help="Coroutine to start_stream")
    define("stop_stream", default=stop_stream, help="Coroutine to stop_stream")
    define("is_stream_active", default=is_stream_active, help="Coroutine to check if stream is active")

    if options.thing_name is None:
        logger.error("No THING_NAME defined")
        sys.exit(1)

    if not os.path.isdir(options.certs_dir):
        logger.error("CERTS_DIR is not a directory: {0}".format(options.certs_dir))
        sys.exit(1)

    app = Application()
    app.listen(options.port, address="0.0.0.0")

    # Initialize the IoT thing.
    iot_thing = IotStreamerThing()
    define("publish_state", default=iot_thing.publish_state, help="publish shadow state")

    def signal_handler(signal, frame):
        logger.info("Stopping current stream")
        stop_stream()

        logger.info('Stopping MQTT thread')
        iot_thing.stop_thing()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    iot_thing.start_thing()

    #TODO: add periodic watcher to verify curr_stream container is alive and restart it if it dies.

    main_ioloop = ioloop.IOLoop.instance()

    main_ioloop.start()
