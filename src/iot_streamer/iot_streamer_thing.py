import os
import sys
import time
import random
import json
import ssl
from tornado import gen
from tornado.options import define, options
import paho.mqtt.client as mqtt

import logging
logger = logging.getLogger(__file__)


# Configure options.
default_client_id = "%s-%d" % ("iot-streamer-thing", random.randrange(100))
define("client_id", default=os.environ.get("CLIENT_ID", None), type=str, help="mqtt client id")
define("thing_name", default=os.environ.get("THING_NAME", None), type=str, help="AWS IoT thing name")
define("iot_endpoint", default=os.environ.get("IOT_ENDPOINT", None), type=str, help="AWS IoT account and region specific endpoint.")
define("iot_port", default=int(os.environ.get("IOT_PORT", "8883")), type=int, help="AWS IoT endpoint port")
define("certs_dir", default="/opt/certs", type=str, help="Directory with IoT thing certificates, rootCA.pem, cert.pem, private.pem")
define("mqtt_connect_timeout", default=int(os.environ.get("MQTT_CONNECT_TIMEOUT", "10")), type=int, help="Initial MQTT connection timeout, main process will exit if timeout is exceeded.")


class IotStreamerThing(object):

    def __init__(self):

        mqttc = mqtt.Client(client_id=options.client_id)
        mqttc.on_connect   = self.on_mqtt_connect
        mqttc.on_subscribe = self.on_mqtt_subscribe
        mqttc.on_message   = self.on_mqtt_message
        mqttc.message_callback_add('$aws/things/%s/shadow/get/rejected' % options.thing_name, self.on_mqtt_thing_get_rejected)
        mqttc.tls_set(
            os.path.join(options.certs_dir, "rootCA.pem"),
            certfile=os.path.join(options.certs_dir, "cert.pem"),
            keyfile=os.path.join(options.certs_dir, "private.pem"),
            tls_version=ssl.PROTOCOL_TLSv1_2,
            ciphers=None
        )

        self.mqttc = mqttc


    def start_thing(self):
        # Start the mqtt loop

        def start_mqtt():
            logger.info("Starting mqtt for thing: {0}".format(options.thing_name))
            self.mqttc.connect(options.iot_endpoint, port=options.iot_port)
            self.mqttc.loop_start()
            time.sleep(1)

            return self.wait_for_mqtt_connected_and_subscribed(options.mqtt_connect_timeout)

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
                        self.mqttc.loop_stop(force=True)

            callback(res)

        start_mqtt_with_retry(lambda res: sys.exit(-1) if not res else logger.info("MQTT connected and subscribed to thing shadow topic."))


    def wait_for_mqtt_connected_and_subscribed(self, timeout):
        count = 0
        while count < timeout:
            if options.mqtt_connected and options.mqtt_subscribed: break

            logger.info("Waiting {0} seconds for MQTT to connect and subscribe.".format(timeout - count))
            time.sleep(1)
            count += 1
        return count < timeout


    def stop_thing(self):
        self.mqttc.loop_stop(force=True)

    @gen.coroutine
    def on_mqtt_connect(self, mqttc, obj, flags, rc):

        if rc == 0:
            logger.info("Subscriber Connection status code: "+str(rc)+" | Connection status: successful")

            #mqttc.message_callback_add('$aws/things/%s/shadow/get/accepted' % options.thing_name, on_mqtt_thing_update)
            #mqttc.message_callback_add('$aws/things/%s/shadow/get/rejected' % options.thing_name, on_mqtt_thing_get_rejected)

            self.mqttc.subscribe([
                ('$aws/things/%s/shadow/update/accepted' % options.thing_name, 1),
                ('$aws/things/%s/shadow/update/rejected' % options.thing_name, 1),
                ('$aws/things/%s/shadow/get/accepted' % options.thing_name, 1),
                ('$aws/things/%s/shadow/get/rejected' % options.thing_name, 1)
            ])

            options.mqtt_connected = True

        elif rc == 1:
            logger.error("Subscriber Connection status code: "+str(rc)+" | Connection status: Connection refused")

        else:
            logger.error("Unknown return code after mqtt connect: '{0}'".format(rc))


    @gen.coroutine
    def on_mqtt_subscribe(self, mqttc, obj, mid, granted_qos):
        logger.info('Subscribed: {0}, {1}, {2}'.format(obj, mid, granted_qos))
        self.mqttc.publish('$aws/things/%s/shadow/get' % options.thing_name, payload='', qos=1, retain=False)
        options.mqtt_subscribed = True
        logger.info("Waiting for initial shadow state message.")

    @gen.coroutine
    def on_mqtt_thing_get_rejected(self, mqttc, obj, msg):
        logger.info("Received thing get rejected from topic: "+msg.topic+" | QoS: "+str(msg.qos)+" | Data Received: "+str(msg.payload))

    @gen.coroutine
    def on_mqtt_thing_update(self, mqttc, obj, msg):
        logger.info("Received thing update from topic: "+msg.topic+" | QoS: "+str(msg.qos)+" | Data Received: "+str(msg.payload))

    @gen.coroutine
    def on_mqtt_message(self, mqttc, obj, msg):
        logger.info("Received message from topic: "+msg.topic+" | QoS: "+str(msg.qos)+" | Data Received: "+str(msg.payload))

        if msg and msg.payload:
            payload = json.loads(msg.payload.decode())
        else:
            logger.error("Invalid message recieved: {0}".format(msg))
            self.mqttc.publish('$aws/things/%s/shadow/get' % options.thing_name, payload='', qos=1, retain=False)
            return

        if 'state' in payload:
            state = payload['state']

            found = False
            for k in ['desired', 'reported']:
                if k in state:

                    if 'url' not in state[k]:
                        logger.warning("'url' not found in device shadow. discarding message.")
                        return

                    url = state[k]['url']
                    logger.debug("{0} URL: {1}".format(k, url))

                    if not url:
                        logger.warning("empty url in shadow state, discarding message.")
                        return

                    # Try to extract quality field.
                    quality = state[k].get("quality", "best")

                    yield options.stop_stream()
                    res, res_msg = yield options.start_stream(url, quality)

                    if res:
                        logger.info("Started stream via MQTT")
                    else:
                        logger.error("Error starting stream: {0}".format(res_msg))
                        #TODO revert to previous stream on error

                    found = True
                    break

            if not found:
                logger.warning("Unsupported state in message, expected 'desired', or 'reported'")

        else:
            logger.warning("No 'state' found in payload.")
