# Email Attachment to CSV

```
{ SES [Email] Event } ==> Email comes in and gets placed into S3
     |
     V
{ S3 Event: s3:ObjectCreated:Put } ==> Trigger Event `lambda_csv_from_email.handler`
     |
     V
{ extracted email CSV attachment } ==> Uploaded to S3
```

NetSuite will periodically produce reports with `price books` and `inventory` of
their tenants and send those reports via email to a pre-determined NewStore
address managed by AWS SES. When the emails come in they are placed into S3, the
S3 bucket will trigger the lambda defined in this project when new files are
added.

The purpose of this lambda is pretty simple: when a new email is detected in S3,
extract the attachment (CSV) and upload it to S3 with a new prefix.

The SES-to-S3 configuration and the S3 trigger will need to be defined outside
of this project.

This project has 2 lambda functions defined to allow for use of the same basic
email attachment extraction functionality for `price books` and `inventory`, as
both follow the same flow.

The `S3*ProcessedPrefix` parameters in the `serverless.aml` will need to be
configured in accordance with the lambdas designated to handle the next steps in
the processing flow: `csv_price_processor` and `netsuite_availability_import`.

