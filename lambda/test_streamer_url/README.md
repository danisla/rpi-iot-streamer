# Livestreamer URL Tester Lambda Function

Lambda function to test if a URL can be streamed by calling `livestreamer.streams`.

Requirements:

 - virtualenv
 - aws cli tools (pip install awscli)
 - jq
 - zip

Setup env:

```
./make_deps.sh
```

Build the lambda package:

```
./make_zip.sh
```

Build and deploy lambda function (after creating function.)

```
./update_code.sh
```

Testing:

```
./invoke.sh <url>
```
