# Shopify Fulfillment Update

- This integration takes events created from the NewStore [event stream](https://apidoc.newstore.io/newstore-cloud/hooks_eventstream.html#event-stream-webhooks-publish-event) webook. The event stream will call this integration for events of type fulfillment_request.items_completed so that the Shopify orders can be updated to fulfilled in Shopify.


## Automatically Process Dead Letter

There are 4 environment variables that should be set to enable the process of the dead letter queue automatically.

  - "ENABLE_AUTO_PROCESSING_DLQ": Set to values 1, yes, y or true to enable the auto processing of dead letter queue, set any other value to disable the feature.
  - "RUN_DLQ_AT": This is the hour at which the dead letter should be automatically processed, it must be an integer in the range of 0-23.
  - "RUN_DLQ_FOR": This is the quantty of minutes that it should process the dead letter for, if the dead letter is to be processed for 30 minutes then put the value as 30, if the dead letter should be processed for 2 hours then set this variable to 120. The value should be a interger greater then 0.
  - "SQS_QUEUE_DLQ": Name of the SQS queue that is the dead letter.


## References

- [NewStore Event Stream](https://apidoc.newstore.io/newstore-cloud/hooks_eventstream.html)

