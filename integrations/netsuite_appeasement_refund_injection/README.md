# NetSuite Integration - Appeasement refund injection implementation

## Description
- Once triggered this lambda reads a SQS queue that contains the events sent by NewStore for the appeasement refunds, event type `refund_request.issued`.
- For each event it fetches the necessary information from NewStore and map it to a CashRefund to be created into NetSuite. There are 2 cases considered:
    - In store order (Cash and Carry): the CashRefund is created from a CashSale
    - In store order with shipping (Endless Aisle): the CashRefund is created as a standalone CashRefund
- The CashRefund contains the payment items for the instruments involved in the refund processing and an additional "Appeasement Refund" item of the type Other Charge to balance out the accounting.

## Order Event to NetSuite Integration

This integration takes events created from the NewStore [event stream](https://apidoc.newstore.io/newstore-cloud/hooks_eventstream.html#event-stream-webhooks-publish-event) webook.

All events from the event stream are received in a very similar manner, which is why they are all included in a single integration that receives the events and push them to the right SQS queue. The `netsuite_event_stream_receiver` acts as an orchestrator and single point of entry for all events; When an event arrives that integration determines which category of event it belongs to then places it into its respective queue for later processing. Each event type has a respective queue and specialized processor/integration. The processor's/integration's jobs are to take the event from the SQS queue and transform it into the format as expected by NetSuite which also means requesting NetSuite to handle certain actions (e.g. issuing a credit note) as a part of the process.


```
{ NewStore Event Stream } ==> `netsuite_event_stream_receiver`
     |
     V
[AWS SQS] <== Events are placed into categorized queues
     |
     V
[Process Event and Transform to NetSuite format] <== Retrieve event from SQS and process (This integration)
     |
     V
{ Update NetSuite }
```

##### Fields
The fields can all be referenced using their generic name in the `scriptId` parameters, keeping them consistent across tenants and environments so long as the generic naming conventions are followed.
##### Objects
NetSuite objects need to be referenced explicitly (e.g. payment processing types, store locations); for these mappings it requires a tightly coupled reference to the NetSuite Internal ID be mapped to the value in NewStore. The Internal ID is a basic auto-incrementing primary key used for pretty much everything in NetSuite, by nature its value is entirely dependent on the order in which objects are added to NetSuite; meaning the values will differ between tenants and environments. In the case of referencing NetSuite objects, a mapping has to be manually maintained between NewStore values and their corresponding NetSuite objects' Internal IDs.


## Build and Deploy

- It's done when the codes are committed, by circle-ci


## Testing

- Run the following commands on the root path for int-frankandoak:
  - `./ci.sh netsuite_appeasement_refund_injection lint`
  - `./ci.sh netsuite_appeasement_refund_injection unittests`


## References

- [NewStore Event Stream](https://apidoc.newstore.io/newstore-cloud/hooks_eventstream.html)

