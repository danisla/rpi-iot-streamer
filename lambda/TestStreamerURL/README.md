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

Testing:

```
./invoke.sh <url>
```
