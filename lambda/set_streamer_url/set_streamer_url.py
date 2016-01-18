from __future__ import print_function

import boto3
import json

client = boto3.client('iot-data')

def set_streamer_url(event, context):

    if 'thingName' not in event:
        print("ERROR: thingName not found in request")
        return {"error": "missing thingName"}

    if 'url' not in event or not event['url']:
        print("ERROR: url not found in request")
        return {"error": "missing url"}

    name = event['thingName']
    url = event['url']
    quality = event.get("quality", "") or "best"

    payload = {
        "state": {
            "desired": {
                "url": url,
                "quality": quality
            }
        }
    }

    print("Seting {0} url to '{1}'".format(name, url))

    response = client.update_thing_shadow(
        thingName=name,
        payload=bytes(json.dumps(payload))
    )
    res = json.loads(response['payload'].read().decode())

    print(res)

    return res
