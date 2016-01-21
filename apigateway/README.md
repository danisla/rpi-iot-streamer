# IoT Streamer API Gateway definition.

Use the provided Swagger JSON export to create the API Gateway stage.

Import using the [`aws-api-gateway-importer`](https://github.com/awslabs/aws-apigateway-importer) tool.

```
./aws-api-import.sh --create ./IotStreamer-prod-swagger-integrations.json
```

A note on exporting/importing.

 - If transferring accounts, make sure to update the lambda function ARNs.
 - Exporting a stage as the `basePath` of the stage, ex: `/prod` set this to `/` to do a 1-1 export/import.
 - API keys are not exported, recreate them manually.
