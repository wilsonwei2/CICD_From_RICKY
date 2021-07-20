# NetSuite Availability Import

## CSV Inventory Import (cii)

Take CSV inventory data generated from Netsuite email extractor and transform
it into a ZIP file to be imported by the `s3-to-newstore` stack.

### Flow

```
[csv: output from email attachment extractor lambda]
  |
  V
{ trigger: ObjectPut on `import_CSVs/FAONSINV_*.csv` }
  |
  V
[lambda: cii_inventory_csv_to_import]
  |
  V
[s3: zip file for stn_step_function]
```

### Environment

The import file is created following the new ATP mode that's documented here:
https://apidoc.newstore.io/newstore-cloud/newstore.html#stock-importing-stock-as-atp-with-timestamps

|Var          | Example                 | Description|
|-------------|-------------------------|------------|
|CFR_TABLE|`completed_fulfillment_requests_timestamps`|DynamoDB table with logical timestamp info|
|S3_BUCKET_NAME|`frankandoak-x-0-newstore-dmz`|
|S3_PREFIX|`queued_for_import/`| S3 output prefix for generated import zips|
|S3_CHUNK_INTERVAL|300|
|S3_CHUNK_SIZE|10000|
|STATE_MACHINE_ARN|`arn:aws:states:us-east-1:XXXX:stateMachine:stn-state-machine`|ARN for step function|

#### S3 Bucket

Requires presence of folder named `queued_for_import`

#### CFR DynamoDB Table

The CFR table requires manual initialization by creating a default object with
the following format:

```
{
  'id': 'main',
  'last_run': '2019-01-01T12:00:00.000Z',
  'last': '1550001641531',
  'current': '1550001641531'
}
```

