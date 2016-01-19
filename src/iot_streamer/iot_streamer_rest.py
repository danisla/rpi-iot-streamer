import os
import random
from tornado import gen, ioloop, web, process
from tornado.options import define, options

import logging
logger = logging.getLogger(__file__)

define("port", default=int(os.environ.get("PORT","8888")), help="run on the given port", type=int)
define("cookie_secret", default="tornadoapp-{0}".format((random.randrange(10000) + 1000)), type=str, help="cookie secret")

################################################################################
# REST Server

class Application(web.Application):
    def __init__(self):
        logger.setLevel(logging.DEBUG if options.debug else logging.INFO)

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
        state = yield options.is_stream_active()
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

        yield options.stop_stream()
        res, msg = yield options.start_stream(url, quality)

        if res:
            logger.info("Started stream via REST")

            options.publish_state(url, quality, update_desired=True)

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

        yield options.stop_stream()
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

            yield options.stop_stream()
            res, msg = yield options.start_stream(url, quality)

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
