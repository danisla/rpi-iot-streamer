#!/usr/bin/env bash

thing=$1
url=$2
[[ -z "${thing}" || -z "${url}" ]] && echo "USAGE: $0 <thing name> <url>" && exit 1

aws iot-data update-thing-shadow \
  --thing-name "${thing}" \
  --payload '{ "state": {"desired": { "url": "'"${url}"'" } } }' .test.out && cat .test.out | jq .
