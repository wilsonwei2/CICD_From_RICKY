#Synchronize transfer order fulfillments from NetSuite to NewStore

```
{ NetSuite saved search }
     ^
     |
[lambda_import_netsuite_transfers transform]
     |
     V
{ NewStore Create ASN }
```

When Frankandoak wants to transfer inventory from a store to another store/DC
they create a Transfer Order in NetSuite which tracks the entire process. Item
Fulfillment records are generated, tied to the Transfer Order, which tracks the
fulfillment (shipping) of the products.

This lambda works with a NetSuite saved search to pull in all Item Fulfillments
that have been generated from a Transfer Order and are in the `shipped` status.
The above criteria guarantees the fulfillment record is related to inventory
transfers and that they are in a state to be "received" by a store.

Shipments are tracked in NewStore as ASNs; store associates can act on ASNs
using the Fulfillment App to record which items were received. This lambda
generates those ASNs from the Item Fulfillment records.

Once actioned upon by an associate, the ASN event triggers the event stream to
fire a `inventory_transaction.items_received` event, which is handled in the
`order_events_to_netsuite\lambda_sqs_inventory_transfer_to_netsuite` lambda.

## Parameter Store
- "{TENANT_NAME}/{STAGE}/newstore": Store the settings for the API credentials to NewStore.
```
{
  "host": "",
  "username": "",
  "password": ""
}
```
- "{TENANT_NAME}/{STAGE}/netsuite": Store the settings for the NetSuite configuration variables.
```
{
    "transfer_order_fulfillments_saved_search_id": "",
    "item_fulfillment_processed_flag_script_id": ""
}
```
- "{TENANT_NAME}/{STAGE}/netsuite_creds": Store the settings for the NetSuite credentials variables.
```
{
    "account_id": "",
    "application_id": "",
    "email": "",
    "password": "",
    "role_id": "",
    "wsdl_url": "",
    "activate_tba": "",
    "disable_login": "",
    "consumer_key": "",
    "consumer_secret": "",
    "token_key": "",
    "token_secret": "",
}
```
- "{TENANT_NAME}/{STAGE}/netsuite/newstore_to_netsuite_locations": Store the mappings for locations from NewStore to NetSuite.
```
{
    "location_1_id_nom": {"id": 1, "ff_node_id": ""},
    "location_2_id_nom": {"id": 2, "ff_node_id": ""}
}
```

## References
- [NewStore ASN Reference](https://apidoc.newstore.io/newstore-cloud/newstore.html#/asns-create-asn)


