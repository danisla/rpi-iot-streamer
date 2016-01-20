#!/usr/bin/env bash

url=$1

[[ -z "${url}" ]] && echo "USAGE $0 <url>" && exit 1

fn="TestStreamerURL"
out="${fn}.out"

aws lambda invoke --function-name "${fn}" --payload '{"url": "'"${url}"'"}' "${out}" && cat "${out}" | jq .
