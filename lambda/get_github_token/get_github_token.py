from __future__ import print_function

import json
import urllib2

GH_CLIENT_ID = "80364444582d4db653e1"
GH_CLIENT_SECRET = "<REDACTED>"


def get_github_token(event, context):

    if "code" not in event:
        return {
            "error": "code not provided"
        }

    code = event["code"]

    url = 'https://www.github.com/login/oauth/access_token' \
                + '?client_id=' + GH_CLIENT_ID + '&client_secret=' + GH_CLIENT_SECRET \
                + '&code=' + code

    try:
        response = urllib2.urlopen(url)
        html = response.read()
    except Exception as e:
        return {
            "error": "error requesting token: " + str(e)
        }

    return {
        "location": "http://localhost:9000/#/?"+html
    }
