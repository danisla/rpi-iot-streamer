from __future__ import print_function

import boto3
import json

client = boto3.client('iot')

def list_things(event, context):

    res = client.list_things(attributeName="type", attributeValue="iot-streamer")
    things = res.get("things", [])

    return {
        "things": things
    }
