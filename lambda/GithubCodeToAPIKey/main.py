from __future__ import print_function

import json
import boto3
import uuid
import urllib2
import re

config = json.load(open("./config.json",'r'))

GH_CLIENT_ID = config["GH_CLIENT_ID"]
GH_CLIENT_SECRET = config["GH_CLIENT_SECRET"]

REQUIRED_REPO = config["REQUIRED_REPO"]
REDIRECT_URL = config["REDIRECT_URL"]

GH_TOKEN_URL = config["GH_TOKEN_URL"]
GH_USER_URL = config["GH_USER_URL"]

IDENTITY_POOL_ID = config["IDENTITY_POOL_ID"]
DEVELOPER_AUTH_PROVIDER = config["DEVELOPER_AUTH_PROVIDER"]

API_KEY = config["API_KEY"]

client = boto3.client('cognito-identity')

pat_token = re.compile("access_token=(.*?)&")

def handler(event, context):

    if "code" not in event:
        return {
            "error": "code not provided"
        }

    code = event["code"]

    url = GH_TOKEN_URL \
                + '?client_id=' + GH_CLIENT_ID + '&client_secret=' + GH_CLIENT_SECRET \
                + '&code=' + code

    try:
        response = urllib2.urlopen(url)
        gh_res = response.read()
        print(gh_res)
        ma = pat_token.match(gh_res)
        if ma:
            gh_tok, = ma.groups()
        else:
            raise Exception("no access_token found in callback, maybe the code has expired.")
    except Exception as e:
        return {
            "error": "error requesting token: " + str(e)
        }

    # Fetch the user profile.
    try:
        headers = {
            "Accept": "application/json",
            "Authorization": "token %s" % gh_tok
        }
        req = urllib2.Request(GH_USER_URL, None, headers)
        response = urllib2.urlopen(req)
        gh_res = response.read()
        user = json.loads(gh_res)
    except Exception as e:
        return {
            "error": "error requesting user profile: " + str(e)
        }

    username = user["login"]
    repos_url = user["repos_url"]

    # Fetch the user repos.
    try:
        headers = {
            "Accept": "application/json",
            "Authorization": "token %s" % gh_tok
        }
        req = urllib2.Request(repos_url, None, headers)
        response = urllib2.urlopen(req)
        gh_res = response.read()
        repos = json.loads(gh_res)
    except Exception as e:
        return {
            "error": "error requesting user repos: " + str(e)
        }

    found_repos = list(filter(lambda x: x["name"] == REQUIRED_REPO and x["owner"]["login"] == username, repos))

    if found_repos:
        print(username +" is owner of " + REQUIRED_REPO)
        return {
            "location": REDIRECT_URL+"?api_key="+API_KEY
        }
    else:
        return {
            "error": "User '%s' is not owner of repo '%s'" % (username, REQUIRED_REPO)
        }
