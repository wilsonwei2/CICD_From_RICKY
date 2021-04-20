# S3 to NewStore (stn)

Listen for inputs as ZIP files in S3 bucket, queue them up to manage the rate
limit, and process them in order to import the data into NewStore's API.

Listens to ObjectCreated:Put and ObjectCreated:Create event on configured S3 bucket.


## Flow

```
[s3: zip data w/ trigger]
  |
  V
[lambda: stn-step-function]
  |
  V
[s3: zip data queue w/ triggers]
  |                           |
  V                           V
[lambda: stn-email-import]  or  [lambda: stn-pricebook-import]
  |                           |
  V                           V
[api: NewStore import]      [api: NewStore import]
```


## Environment

### S3 Triggers

Using `arn:aws:s3:::goorin-brothers-x-0-newstore-dmz` bucket. Navigate to "properties"
and then "events" and define the following triggers:

1. `stn-pricebook-import`
  - events: PUT, COPY
  - prefix: `import_files/availabilities/`
  - suffix: `zip`
  - send to: 'Lambda Function'
  - Lambda: `stn-pricebook-import`

2. `stn-email-import`
  - events: PUT, COPY
  - prefix: `import_files/availabilities/`
  - suffix: `zip`
  - send to: 'Lambda Function'
  - Lambda: `stn-email-import`

NOTE: These triggers require permission from the Lambdas in order to be
triggered. These are defined as `AWS::Lambda::Permission` in the `template.yml`.


### Lambda Environment Variables

1. `stn-pricebook-import`
  - BASE_URL = `https://goorin-brothers.x.newstore.net` (default)
  - ENTITIES = `availabilities` (default; format is CSV without spaces)
  - NS_PASSWORD = manual definition
  - NS_USERNAME = manual definition
  - PROVIDER = `glue` (default)

2. `stn-email-import`
  - BASE_URL = `https://goorin-brothers.x.newstore.net` (default)
  - ENTITIES = `availabilities` (default; format is CSV without spaces)
  - NS_PASSWORD = manual definition
  - NS_USERNAME = manual definition
  - PROVIDER = `glue` (default)

3. `stn-step-function`
  - DESTINATION_BUCKET = `goorin-brothers-x-0-newstore-dmz` (default)
  - DESTINATION_PREFIX = `import_files/availabilities` (default)

## Dependencies

1. `csv-prices-processor` calls `stn-step-function` directly by name
and as such needs to be kept in sync if the name is changed.

2. `csv-inventory-import` calls `stn-step-function` directly by name
and as such needs to be kept in sync if the name is changed.
