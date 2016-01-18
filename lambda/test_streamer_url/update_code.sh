#!/usr/bin/env bash

fn="TestStreamerURL"
fnz="fileb://$(pwd)/test_streamer_url_lambda.zip"

./make_zip.sh && \
  aws lambda update-function-code --function-name "$fn" --zip-file "${fnz}" --publish
