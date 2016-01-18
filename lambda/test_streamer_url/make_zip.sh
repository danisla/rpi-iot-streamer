#!/usr/bin/env bash

f="./test_streamer_url.py"
ZIP="$(pwd)/test_streamer_url_lambda.zip"

zip "${ZIP}" "${f}"

cd pyenv/lib/python2.7/site-packages
zip -r -u "${ZIP}" .
cd ->/dev/null

echo "INFO: Lambda zip package created: ${ZIP}"
