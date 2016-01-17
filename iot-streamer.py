import os
import json
import sys
import ssl
import random
import paho.mqtt.client as mqtt
from tornado import gen, ioloop, web, process
import tornado.options
from tornado.options import define, options
from bson import json_util
import shlex
import time
import signal
import docker
import re
import livestreamer
from livestreamer import NoPluginError, PluginError

###################################
# Logging setup

import logging
logger = logging.getLogger()
log_level = logging.INFO
if os.environ.get("DEBUG","False").lower() == "true":
    log_level = logging.DEBUG

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

logger.setLevel(log_level)

###################################

default_client_id = "%s-%d" % ("iot-streamer-thing", random.randrange(100))

# Program options.
define("debug", default=os.environ.get("DEBUG","false").lower() == "true", help="Enable debugging")
define("player_docker_image", default=os.environ.get("PLAYER_DOCKER_IMAGE","danisla/rpi-omxplayer:latest"), help="docker image tag for playing stream url")
define("rpi_player", default=os.environ.get("RPI_PLAYER","true").lower() == "true", type=bool, help="add additional docker args when starting player container to support RPI")
define("resolve_url", default=os.environ.get("RESOLVE_URL","true").lower() == "true", type=bool, help="use livestreamer to resolve streamable url")
define("certs_dir", default="./certs", type=str, help="Directory with IoT thing certificates, rootCA.pem, cert.pem, private.pem")
define("port", default=int(os.environ.get("PORT","8888")), help="run on the given port", type=int)
define("cookie_secret", default="tornadoapp-{0}".format((random.randrange(10000) + 1000)), type=str, help="cookie secret")
define("thing_name", default=os.environ.get("THING_NAME", None), type=str, help="AWS IoT thing name")
define("client_id", default=os.environ.get("CLIENT_ID", None), type=str, help="mqtt client id")
define("iot_endpoint", default=os.environ.get("IOT_ENDPOINT", None), type=str, help="AWS IoT account and region specific endpoint.")
define("iot_port", default=int(os.environ.get("IOT_PORT", "8883")), type=int, help="AWS IoT endpoint port")
define("grace_period", default=int(os.environ.get("GRACE_PERIOD", "10")), type=int, help="Player startup grace period before declaring error")
define("mqtt_connect_timeout", default=int(os.environ.get("MQTT_CONNECT_TIMEOUT", "10")), type=int, help="Initial MQTT connection timeout, main process will exit if timeout is exceeded.")

define("docker_host", default=os.environ.get("DOCKER_HOST", None), type=str, help="If specified, connect to this docker host, default is socket")
define("docker_tls_ca", default=os.environ.get("DOCKER_TLS_CA", os.environ.get("DOCKER_CERT_PATH","")+"/ca.pem"), type=str, help="TLS CA cert for docker host")
define("docker_tls_cert", default=os.environ.get("DOCKER_TLS_CERT", os.environ.get("DOCKER_CERT_PATH","")+"/cert.pem"), type=str, help="TLS cert for docker host")
define("docker_tls_key", default=os.environ.get("DOCKER_TLS_KEY", os.environ.get("DOCKER_CERT_PATH","")+"/key.pem"), type=str, help="TLS key for docker host")

# Name of currently running container.
curr_container_name = '.*curr_stream.*'

###############################################################################

def get_docker_client():

    docker_host = options.docker_host
    docker_tls_ca = options.docker_tls_ca
    docker_tls_cert = options.docker_tls_cert
    docker_tls_key = options.docker_tls_key

    if docker_host:

        tls_config = None

        if docker_tls_ca:

            if not os.path.exists(docker_tls_ca):
                raise Exception("Cannot read docker ca file: %s" % docker_tls_ca)

            if not os.path.exists(docker_tls_cert):
                raise Exception("Cannot read docker cert file: %s" % docker_tls_cert)

            if not os.path.exists(docker_tls_key):
                raise Exception("Cannot read docker key file: %s" % docker_tls_key)

            tls_config = docker.tls.TLSConfig(
                ca_cert=docker_tls_ca,
                client_cert=(docker_tls_cert, docker_tls_key),
                verify=True
            )

            if docker_host.startswith("tcp://"):
                docker_host = docker_host.replace("tcp://","https://")
            elif not docker_host.startswith("https://"):
                docker_host = "https://" + docker_host

            logger.debug("Docker host: " + docker_host)

            cli = docker.Client(base_url=docker_host, tls=tls_config, version='auto')

        else:
            cli = docker.Client()

    return cli


def find_containers(pat_s, all=False):
    pat = re.compile(pat_s)
    cli = get_docker_client()
    containers = []

    for c in cli.containers(all=all):
        for n in c["Names"]:
            if pat.match(n):
                containers.append(c)
    return containers

################################################################################


################################################################################
# REST Server

class Application(web.Application):
    def __init__(self):

        define(name="stream", default=None, help="instance of the currently running stream", type=process.Subprocess)
        define(name="url", default=None, help="current url", type=str)

        handlers = [
            (r"/", MainHandler),
            (r"/start", StartStreamHandler),
            (r"/stop", StopStreamHandler),
            (r"/restart", ReStartStreamHandler)
        ]
        settings = dict(
            cookie_secret=options.cookie_secret,
            xsrf_cookies=True,
            debug=options.debug
        )
        web.Application.__init__(self, handlers, **settings)

        logger.info("Application initialized on port {0}".format(options.port))

        if options.debug:
            logger.info("Debug mode enable.")


class MainHandler(web.RequestHandler):

    @gen.coroutine
    def get(self):
        state = yield is_stream_active()
        self.write({
            "status": "ok",
            "curr_url": options.curr_url,
            "active": True if state and options.curr_url else False
        })


class StartStreamHandler(web.RequestHandler):

    @gen.coroutine
    def get(self):
        url = str(self.get_query_argument("url"))
        quality = str(self.get_query_argument("quality", "best"))

        yield stop_stream()
        res, msg = yield start_stream(url, quality)

        if res:
            logger.info("Started stream via REST")

            self.write({
                "status": "started",
                "url": url
            })
        else:
            logger.error("Error starting stream via REST")

            self.set_status(500)
            self.write({
                "status": "error",
                "msg": msg
            })


class StopStreamHandler(web.RequestHandler):

    @gen.coroutine
    def get(self):

        yield stop_stream()
        logger.info("Stopped stream via REST")

        self.write({
            "status": "stopped"
        })


class ReStartStreamHandler(web.RequestHandler):

    @gen.coroutine
    def get(self):

        url = options.curr_url
        quality = options.curr_quality

        if url and quality:

            yield stop_stream()
            res, msg = yield start_stream(url, quality)

            if res:
                logger.info("Restarted stream via REST")

                self.write({
                    "status": "restarted",
                    "url": url
                })
            else:
                logger.error("Error restarting stream via REST")

                self.set_status(500)
                self.write({
                    "status": "error",
                    "msg": msg
                })
        else:
            logger.warning("Could not restart stream because no url is set.")

            self.set_status(400)
            self.write({
                "status": "error",
                "msg": "no url currently set"
            })


################################################################################


################################################################################
# Async functions

@gen.coroutine
def create_stream_container(url, quality):
    cli = get_docker_client()

    container = None
    docker_image = None

    docker_image = options.player_docker_image

    if url.startswith("rtsp"):
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

            url = stream.url

    container = None
    try:

        devices = []
        if options.rpi_player:
            for d in ["/dev/vchiq", "/dev/fb0", "/dev/snd"]:
                devices.append({
                    "PathOnHost": d,
                    "PathInContainer": d,
                    "CgroupPermissions": "mrw"
                })

        binds = []
        if options.rpi_player:
            for v in ["/opt/vc"]:
                binds.append(v+":"+v+":ro")

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

        container = cli.create_container(
            image=docker_image,
            command=url,
            ports=[8000],
            detach=True,
            name="curr_stream",
            host_config=host_config
        )
    except Exception as e:
        logger.error("Error creating docker container: {0}".format(e))

    if container:
        logger.info("Created container with image: '{0}'".format(docker_image))
        return container
    else:
        return None


@gen.coroutine
def start_container(container_id, grace_period=None):

    cli = get_docker_client()

    try:
        cli.start(container_id)
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

        #logger.info("Starting docker container with image: '{0}', url: '{1}'".format(docker_image, url))

        res = yield start_container(container_id, grace_period=options.grace_period)
        if res:
            options.curr_url = url
            options.curr_quality = quality

            return True, "Container started"
        else:
            return False, "Error starting stream container"

    else:
        return False, "Could not create docker container for url '{0}'".format(url)


@gen.coroutine
def is_stream_active():

    logger.info("Checking for active containers matching name: '{0}'".format(curr_container_name))

    c = find_containers(curr_container_name)

    return len(c) > 0


@gen.coroutine
def stop_stream():
    cli = get_docker_client()

    # Kill and remove existing containers.
    curr_containers = find_containers(curr_container_name, all=True)
    for c in curr_containers:
        i = c["Id"]
        if c['Status'].startswith("Up"):
            logger.info("Killing container: '{0}'".format(c["Names"]))
            cli.kill(i)

        logger.info("Removing container: '{0}'".format(c["Names"]))
        cli.remove_container(i)


@gen.coroutine
def on_mqtt_connect(mqttc, obj, flags, rc):

    if rc == 0:
        logger.info("Subscriber Connection status code: "+str(rc)+" | Connection status: successful")
        mqttc.subscribe([('$aws/things/%s/shadow/update/accepted' % options.thing_name, 1) , ('$aws/things/%s/shadow/get/accepted' % options.thing_name, 1)])

        options.mqtt_connected = True

    elif rc == 1:
        logger.error("Subscriber Connection status code: "+str(rc)+" | Connection status: Connection refused")

    else:
        logger.error("Unknown return code after mqtt connect: '{0}'".format(rc))


@gen.coroutine
def on_mqtt_subscribe(mqttc, obj, mid, granted_qos):
    logger.info('Subscribed: {0}, {1}, {2}'.format(obj, mid, granted_qos))
    mqttc.publish('$aws/things/%s/shadow/get' % options.thing_name, payload='', qos=1, retain=False)
    options.mqtt_subscribed = True

@gen.coroutine
def on_mqtt_message(mqttc, obj, msg):
    logger.debug("Received message from topic: "+msg.topic+" | QoS: "+str(msg.qos)+" | Data Received: "+str(msg.payload))

    payload = json.loads(msg.payload.decode())

    if 'state' in payload:
        state = payload['state']

        found = False
        for k in ['desired', 'reported']:
            if k in state:

                url = state[k].get('url', None)
                logger.debug("{0} URL: {1}".format(k, url))

                # Try to extract quality field.
                quality = state[k].get("quality", "best")

                yield stop_stream()
                res, res_msg = yield start_stream(url, quality)

                if res:
                    logger.info("Started stream via MQTT")
                else:
                    logger.error("Error starting stream: {0}".format(res_msg))

                found = True
                break

        if not found:
            logger.warn("Unsupported state in message, expected 'desired', or 'reported'")

    else:
        logger.warn("No 'state' found in payload.")

def wait_for_mqtt_connected_and_subscribed(timeout):
    count = 0
    while count < timeout:
        if options.mqtt_connected and options.mqtt_subscribed: break
        logger.info("Waiting {0} seconds for MQTT to connect and subscribe.".format(timeout - count))
        time.sleep(1)
        count += 1
    return count < timeout

################################################################################

if __name__ == "__main__":

    options.parse_command_line()

    define("curr_url", default=None, help="Current URL being displayed")
    define("curr_quality", default=None, help="Current stream quality being displayed")

    define("mqtt_connected", default=False, help="Indicator that mqtt connect was successful")
    define("mqtt_subscribed", default=False, help="Indicator that mqtt subscribe was successful")

    if options.thing_name is None:
        logger.error("No THING_NAME defined")
        sys.exit(1)

    if not os.path.isdir(options.certs_dir):
        logger.error("CERTS_DIR is not a directory: {0}".format(options.certs_dir))
        sys.exit(1)

    app = Application()
    app.listen(options.port, address="0.0.0.0")

    # Configure and connect to MQTT
    mqttc = mqtt.Client(client_id=options.client_id)
    mqttc.on_connect   = on_mqtt_connect
    mqttc.on_subscribe = on_mqtt_subscribe
    mqttc.on_message   = on_mqtt_message
    mqttc.tls_set(
        os.path.join(options.certs_dir, "rootCA.pem"),
        certfile=os.path.join(options.certs_dir, "cert.pem"),
        keyfile=os.path.join(options.certs_dir, "private.pem"),
        tls_version=ssl.PROTOCOL_TLSv1_2,
        ciphers=None
    )

    def signal_handler(signal, frame):
        logger.info("Stopping current stream")
        stop_stream()

        logger.info('Stopping MQTT thread')
        mqttc.loop_stop(force=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    def start_mqtt():
        logger.info("Starting mqtt for thing: {0}".format(options.thing_name))
        mqttc.connect(options.iot_endpoint, port=options.iot_port)
        mqttc.loop_start()
        time.sleep(1)

        return wait_for_mqtt_connected_and_subscribed(options.mqtt_connect_timeout)

    def start_mqtt_with_retry(callback=None):
        mqtt_retries = 3
        for retry in range(mqtt_retries):
            res = start_mqtt()
            if res:
                break
            else:
                if (retry + 1) == mqtt_retries:
                    logger.error("MQTT connect failed after {0} attempts.".format(mqtt_retries))
                else:
                    logger.warning("MQTT connect and subscribe timeout, retrying {0} of {1}.".format(retry+2, mqtt_retries))
                    mqttc.loop_stop(force=True)

        callback(res)

    start_mqtt_with_retry(lambda res: sys.exit(-1) if not res else logger.info("MQTT connected and subscribed to thing shadow topic."))

    main_ioloop = ioloop.IOLoop.instance()

    main_ioloop.start()
