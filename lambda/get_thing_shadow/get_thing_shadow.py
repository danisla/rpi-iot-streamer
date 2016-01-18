from __future__ import print_function

import boto3
import json

client = boto3.client('iot-data')

def get_thing_shadow(event, context):
    print(context)

    if 'thingName' not in event:
        print("ERROR: thingName not found in request")
        return

    name = event['thingName']

    print("Fetching shadow for: {0}".format(name))

    shadow = json.loads(client.get_thing_shadow(thingName=name)['payload'].read().decode())

    print("Got thing shadow for: {0}".format(name))

    return shadow
