# Marine Layer - Pricebook processor

```
{ S3 Event: s3:ObjectCreated:Put } ==> Trigger Event `price_import_processor.handler`
     |
     V
[transform]
     |
     V
[upload processed pricebook to S3]
     |
     V
{ processed price book data } ==> Trigger StepFunction `SFN_CLIENT.start_execution`
```

Price books for Marine Layer are received through email attachments, those attachments
are stripped and placed into S3 which is where this lambdas process begins.

Add the S3 Trigger, using AWS S3 Notifications consule.

The `price_import_processor` is triggered when a file is placed into S3 that matches
the criteria configured in the serverless.yml file.

Once triggered this lambda will pull the file from S3 and use the transformer.py class to transform,
the data into the format expected by the Marine Layer.

Link to the document:
[NewStore Price books](https://goodscloud.atlassian.net/wiki/spaces/ML/pages/1494155351/Prices)

The processed price book data is
chunked into small sections, zipped and uploaded to a different S3 bucket, then
a step function is called to continue acting on the zipped price book data.

Eventually the price book data will be imported to NewStore by some external
process.

NOTE: The S3 bucket will need to be configured to trigger this lambda when it
recognizes a new CSV file get added. The `suffix` and `prefix` filters will be
set as a part of this trigger; their values will need to come from the tenant/
project SA.

## Build and Deploy



## Testing



## References

- [Marine Layer Implementaion Price books](https://goodscloud.atlassian.net/wiki/spaces/ML/pages/1481048332/Price+book)

