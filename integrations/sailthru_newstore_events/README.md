NS Events to Sailthru:

This integration listens to the NewStore event stream, picking up the relevant events,
performs mapping on the data, and sends it to Sailthru by invoking the Sailthru client lambda named frankandoak-sailthru.
#LAMBDAS
- frankandoak-sailthru-event-receive: receives event from event stream integration and pushes relevant events to corresponding queue
- frankandoak-shipping-confirmation-email: reads event data from queue, performs data mapping, and calls invoke Sailthru client lambda (burton-sailthru)
- frankandoak-sailthru-webhook: checks daily to see if event stream integration exists and is updated


##Parameter Store
- {tenant}/{stage}/sailthru_templates: contains template names for different events based on country
{ "template_us": {
"order_cancel": "US Order Cancellation",
"ship_confirmation": "US Shipping Confirmation"
},
"template_ca": {
"order_cancel": "CA Order Cancellation",
"ship_confirmation": "CA Shipping Confirmation"
},
"template_eu": {
"order_cancel": "EU Order Cancellation",
"ship_confirmation": "EU Shipping Confirmation"
} }

- {tenant}/{stage}/sailthru_credentials: contains credentials (client id and secret) to invoke Sailthru client
{ "US": {
	"id":""
	"secret":""
},
"CA": {
	"id":"",
	"secret":""
},
"EU": {
	"id":"",
	"secret":""
},
"JP": {
	"id":"",
	"secret":""
} }


##Lambda environment variables
- burton-sailthru-event-receive
SAILTHRU_QUEUE: name of queue where NS events is dumped to and received from by processing lambdas

- burton-shipping-confirmation-email
TENANT_NAME: name of tenant
NS_STAGE: deployment stage
SAILTHRU_QUEUE: name of queue where NS events is dumped to and received from by processing lambdas
INVOKE_SAILTHRU_LAMBDA: name of lambda that invokes Sailthru client
NEWSTORE_CREDS_PARAM: path to the NewStore credentials parameter in Param Store
SAILTHRU_TEMPLATES_PARAM: path to the Sailthru templates config parameter in Param Store

- burton-sailthru-webhook
SAILTHRU_AWSAPI_URL: AWS Gateway endpoint for lambda burton-sailthru-event-receive
TENANT_NAME: name of tenant
NS_STAGE: deployment stage
SAILTHRU_HOOK_NAME: name of event stream integration hook
EVENTS_TO_FILTER: events to be filtered by the integration hook
NEWSTORE_CREDS_PARAM: path to the NewStore credentials parameter in Param Store
