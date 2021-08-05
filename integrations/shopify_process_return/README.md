# Shopify Process Return

Process returns from Shopify and create them in NewStore.

## Specs
This integration is conposed with 4 different lambdas, receive and process the return from Shopify. There is also a mechanism to pick the refunds that are missing. The final lambda is a to register and mantain the webhook connected in Shopify;

### Receive Return
This lambda will require a `shopify_secret`, this is the value of the shared_key of your private app credentials;
The Lambda will just validate the payload and drop the message to a queue;

### Process Return
Please provide the parameter of the `warehouse` where you want the refunds will be processed by. Currently we don't have means to map what Shopify return sent us to our locations;

### Sync Job
Please provide the number of hours `HOURS_TO_CHECK` to go back and try to fetch refunds;

### Register Webhook
This lambda will run once a day a validate if the webhook is up, if not it will register it back;

#### Extra Info
Currently when the process lambda creates a historical refund in Newstore, it passes in the extended_attributes the shopify refund id, this will then be used after to validate if we already processed this refund.


