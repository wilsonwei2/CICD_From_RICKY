# Fulfillment Event to NetSuite Integration

This integration takes events created from the NewStore
[event stream](https://apidoc.newstore.io/newstore-cloud/hooks_eventstream.html#event-stream-webhooks-publish-event)
webhook. The event stream will call the netsuite event stream receiver integration
for several different order event types:
1. order created
1. order opened
1. return processed
1. order item cancelled
1. fulfillment request completed
1. item transfers
1. appeasement refunds

This integration will read the events from a SQS queue that is feeded by the netsuite event stream receiver.

```
{ NewStore Event Stream } ==> `netsuite event stream receiver`
     |
     V
[AWS SQS] <== Events are placed into categorized queues
     |
     V
[Process Event and Transform to NetSuite format] <== Retrieve event from SQS and process
     |
     V
{ Update NetSuite }
```

### Items Completed
If the event message pushed to `lambda_event_stream_to_sqs` has an `event_type` value of
`fulfillment_request.items_completed` and the message does not represent an in-store handover, it is interpreted as a
request to create an ItemFulfillment record in NetSuite. The message body
is sent to the configured `SQS_FULFILLMENT` and batch-processed by the
`sqs_item_fulfillment_to_netsuite` lambda.

#### Lambda `sqs_item_fulfillment_to_netsuite`
This lambda is responsible for reading messages from the configured `SQS_FULFILLMENT` queue, transforming them into
ItemFulfillment objects, and injecting them into NetSuite.

The created ItemFulfillment is made from a reference to the original Sales Order. If no Sales Order is found the lambda
fails to process the message. Alternatively, if the ItemFulfillment record has already been injected, the message is
considered finished and no additional record is injected.

## References
- [NewStore Event Stream](https://apidoc.newstore.io/newstore-cloud/hooks_eventstream.html)
