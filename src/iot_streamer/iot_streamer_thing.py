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

    # Handlers for IoT Thing Shadow flow
    # http://docs.aws.amazon.com/iot/latest/developerguide/thing-shadow-mqtt.html

    def __init__(self):
        logger.setLevel(logging.DEBUG if options.debug else logging.INFO)

        self.shadow = None

        mqttc = mqtt.Client(client_id=options.client_id)
        mqttc.on_connect   = self.on_connect
        mqttc.on_subscribe = self.on_subscribe
        mqttc.on_message   = self.on_message

        ### /shadow/update handlers ###
        # Response to /update
        mqttc.message_callback_add('$aws/things/%s/shadow/update/accepted' % options.thing_name, self.on_update_accepted)
        # Rejection from /update
        mqttc.message_callback_add('$aws/things/%s/shadow/update/rejected' % options.thing_name, self.on_update_rejected)
        # Delta broadcast
        mqttc.message_callback_add('$aws/things/%s/shadow/update/delta' % options.thing_name, self.on_update_delta)

        ### /shadow/get handlers ###
        # Response to /shadow/get
        mqttc.message_callback_add('$aws/things/%s/shadow/get/accepted' % options.thing_name, self.on_get_accepted)
        # Rejection from /shadow/get
        mqttc.message_callback_add('$aws/things/%s/shadow/get/rejected' % options.thing_name, self.on_get_rejected)

        ### /shadow/delete
        # Not applicable

        mqttc.tls_set(
            os.path.join(options.certs_dir, "rootCA.pem"),
            certfile=os.path.join(options.certs_dir, "cert.pem"),
            keyfile=os.path.join(options.certs_dir, "private.pem"),
            tls_version=ssl.PROTOCOL_TLSv1_2,
            ciphers=None
        )

        self.mqttc = mqttc

        self.get_shadow_retry_count = 0
        self.get_shadow_max_retries = 3


    def start_thing(self):
        # Start the mqtt loop

        def start_mqtt():
            logger.info("Starting mqtt for thing: {0}".format(options.thing_name))
            self.mqttc.connect(options.iot_endpoint, port=options.iot_port)
            self.mqttc.loop_start()
            time.sleep(1)

            return self.wait_for_connect_and_subscribe(options.mqtt_connect_timeout)

        def start_with_retry(callback=None):
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

        start_with_retry(lambda res: sys.exit(-1) if not res else logger.info("MQTT connected and subscribed to thing shadow topic."))


    def wait_for_connect_and_subscribe(self, timeout):
        count = 0
        while count < timeout:
            if options.mqtt_connected and options.mqtt_subscribed: break

            logger.info("Waiting {0} seconds for MQTT to connect and subscribe.".format(timeout - count))
            time.sleep(1)
            count += 1
        return count < timeout


    def stop_thing(self):
        self.mqttc.loop_stop(force=True)


    def on_connect(self, mqttc, obj, flags, rc):

        if rc == 0:
            logger.info("Subscriber Connection status code: "+str(rc)+" | Connection status: successful")

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

    def on_subscribe(self, mqttc, obj, mid, granted_qos):
        logger.info('Subscribed: {0}, {1}, {2}'.format(obj, mid, granted_qos))
        self.__get_thing_shadow()
        options.mqtt_subscribed = True
        logger.info("Waiting for initial shadow state message.")
        self.__initial_state_watchdog(10)


    @gen.coroutine
    def __initial_state_watchdog(self, timeout, retries=3):
        retry=0
        count = 0
        while not self.shadow is not None:
            count += 1
            nxt = gen.sleep(1)

            logger.info("Waiting for initial shadow: {0}s remaining".format(timeout-count))

            if count >= timeout:
                if retry >= retries:
                    logger.error("Max retries exceeded while waiting for initial shadow state.")
                    break

                retry += 1
                logger.warning("Initial state watchdog expired, requesting shadow state again ({0}/{1}).".format(retry, retries))
                self.__get_thing_shadow()
                count = 0

            yield nxt


    def __parse_payload(self, msg):
        return json.loads(msg.payload.decode())


    def __get_thing_shadow(self):
        self.mqttc.publish('$aws/things/%s/shadow/get' % options.thing_name, payload='', qos=1)


    def publish_state(self, url, quality, update_desired=False):
        logger.info("Publishing state update: url='{0}', quality='{1}'".format(url, quality))
        payload = {
            "state": {
                "reported": {
                    "url": url,
                    "quality": quality
                }
            }
        }
        if update_desired:
            payload["state"]["desired"] = payload["state"]["reported"]

        self.mqttc.publish('$aws/things/%s/shadow/update' % options.thing_name, payload=json.dumps(payload))


    @gen.coroutine
    def __resolve_state(self):
        # This coroutine actually diffs the shadow state with the actual state and starts the stream if needed.
        # If the stream was start successfully then the new reported state is published.

        if self.shadow is None:
            logger.error("__resolve_state called before shadow was set.")
            return

        logger.debug(self.shadow)

        def get_field(name, default=None):
            return self.shadow['state'].get('desired', self.shadow['state'].get('reported', {})).get(name, default)

        # Get url and quality from shadow 'desired' or 'reported'
        shadow_url = get_field("url")
        quality = get_field("quality", "best")

        if shadow_url is None:
            logger.error("No 'url' state found in thing shadow")
            return

        if options.curr_url != shadow_url or options.curr_quality != quality:
            if shadow_url:
                logger.info("old url: '{0}', new url: '{1}'".format(options.curr_url, shadow_url))

                yield options.stop_stream()
                res, res_msg = yield options.start_stream(shadow_url, quality)

                if res:
                    logger.info("Started stream via MQTT")
                    self.publish_state(shadow_url, quality)
                else:
                    logger.error("Error starting stream: {0}".format(res_msg))
                    #TODO revert to previous stream on error

            else:
                logger.warning("Stopping stream because shadow url is empty.")
                yield options.stop_stream()
                self.publish_state(shadow_url, quality)
        else:
            logger.info("shadow and state are in sync, no action.")


    def on_update_accepted(self, mqttc, obj, msg):
        logger.debug("Received /update/accepted msg: {0}".format(msg.payload))
        self.shadow.update(self.__parse_payload(msg))
        self.__resolve_state()


    def on_update_rejected(self, mqttc, obj, msg):
        logger.warning("Received /update/rejected msg: {0}".format(msg.payload))


    def on_get_accepted(self, mqttc, obj, msg):
        logger.debug("Received /get/accepted msg: {0}".format(msg.payload))
        self.shadow = self.__parse_payload(msg)
        self.__resolve_state()


    def on_update_delta(self, mqttc, obj, msg):
        logger.info("Received /update/delta msg: {0}".format(msg))
        self.shadow.update(self.__parse_payload(msg))
        self.__resolve_state()


    def on_get_rejected(self, mqttc, obj, msg):
        logger.warning("Received /get/rejected msg: {0}".format(msg))

        if self.shadow is None and self.get_shadow_retry_count < self.get_shadow_max_retries:
            # Retry the initial shadow request.
            self.get_shadow_retry_count += 1
            self.__get_thing_shadow()


    def on_message(self, mqttc, obj, msg):
        logger.warning("Received unhandled message from topic: "+msg.topic+" | QoS: "+str(msg.qos)+" | Data Received: "+str(msg.payload))
