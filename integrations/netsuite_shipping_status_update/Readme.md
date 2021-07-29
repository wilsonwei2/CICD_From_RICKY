# NetSuite Integration for shipped (fulfilled) items in DC

This integration covers the usual case that items are shipped and fulfilled from DC. In this case an ItemFulfillment
is created in Netsuite, and these ItemFulfillments need to synced back into NewStore to create Shipments including
the tracking and carrier data. This process also triggers other events, like sending out the shipping email or
capture the payment.

A saved search is setup in Netsuite to query non-injected ItemFulfillments from DC which are shipped.

After the search is done, we will update the data in NewStore and update the ItemFulfillment with a custom attribute (boolean) that it has been synced to NewStore. This will exclude it from the saved search and won’t be send again.

```
{ NewStore Event Trigger } ==> `frankandoak-shipping-status-update-trigger`
     |
     V
[ AWS Lambda ] ==> `frankandoak-netsuite_shiping_status_to_newstore`
     |
     V
{ Get Shipped Item Fulfillments from Netsuite via SavedSearch }
     |
     V
{ Extract the data from the Saved Search; query ItemFulfillment details and SalesOrder from Netsuite
to get all the IDs; extract the Carrier, Tracking Link information }
     |
     V
{ Query the Fulfillments from NewStore via GraphQL and map the Netsuite data against it; create the Shipment
in NewStore }
     |
     V
{ Update each ItemFulfillment in NetSuite and mark as processed }
```

