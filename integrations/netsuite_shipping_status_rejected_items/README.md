# NetSuite Integration for rejected (non-shipped) items

It can happen that an order should be fulfilled by the DC, but the shipping is rejected, e.g.
if there is not inventory available or products are damaged. In this case we need to update the
NST fulfillment / item rejection status and eventually trigger another routing for the item or cancel it.

A saved search is setup in Netsuite to query Sales Orders and Sales Order Items fulfilled from DC which are rejected.

After the search is done, we will update the data in NewStore and update the item with a custom attribute (boolean) that it has been synced to NewStore. This will exclude it from the saved search and won’t be send again.

```
{ NewStore Event Trigger } ==> `frankandoak-netsuite-rejected-items-to-newstore-trigger`
     |
     V
[ AWS Lambda ] ==> `frankandoak-netsuite_rejected_items_to_newstore`
     |
     V
{ Get Rejected Items from Netsuite via SavedSearch }
     |
     V
[ AWS Lambda ] ==> `frankandoak-netsuite_rejected_items_to_newstore` ==> process each item and mark rejected in NewStore
     |
     V
{ Update each item in NetSuite and mark as processed }
```


