from __future__ import print_function

import boto3
import json
from botocore.exceptions import ClientError

client = boto3.client('iot-data')

def get_thing_shadow(event, context):
    print(context)

    if 'thingName' not in event:
        print("ERROR: thingName not found in request")
        return

    name = event['thingName']

    print("Fetching shadow for: {0}".format(name))

    try:
        shadow = json.loads(client.get_thing_shadow(thingName=name)['payload'].read().decode())
    except ClientError as e:
        return {
            "errorType": "ClientError",
            "errorMessage": str(e)
        }

    print("Got thing shadow for: {0}".format(name))

    return shadow
