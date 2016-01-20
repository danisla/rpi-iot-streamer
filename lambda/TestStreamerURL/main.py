from __future__ import print_function

import json
import livestreamer
from livestreamer import NoPluginError, PluginError

def handler(event, context):

    if 'url' not in event or not event['url']:
        print("ERROR: url not found in request")
        return {"error": "missing url"}

    url = event["url"]

    res = {
        "streamable": False,
        "streams": {},
        "msg": ""
    }

    if url.startswith("rtsp") or url.startswith("rtmp"):
        # URL should be streamable, no further resolution needed.
        res["streamable"] = True

    else:
        # Attempt to get streamable url via livestreamer
        streams = None
        try:
            streams = livestreamer.streams(url)
            for q,u in streams.items():
                try:
                    streams[q] = u.url
                except Exception as e:
                    streams[q] = u
        except NoPluginError:
            res["msg"] = "URL is not yet supported."
        except PluginError as err:
            res["msg"] = "Unable to process URL."

        if streams:
            res["streamable"] = True
            res["streams"] = { k:str(v) for k,v in streams.items() }
        else:
            res["msg"] = "No streams found on URL"

    return res
