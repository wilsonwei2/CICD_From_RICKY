# Return Events to NetSuite Integration

This integration takes return events created from the NewStore [event stream](https://apidoc.newstore.io/newstore-cloud/hooks_eventstream.html#event-stream-webhooks-publish-event) webhook that are saved to a SQS queue
and injects them into NetSuite as CashRefunds/CreditMemos.

```
{ NewStore Event Stream } ==> `frankandoak-event-stream-to-sqs lambda integration`
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

## References

- [NewStore Event Stream](https://apidoc.newstore.io/newstore-cloud/hooks_eventstream.html)
