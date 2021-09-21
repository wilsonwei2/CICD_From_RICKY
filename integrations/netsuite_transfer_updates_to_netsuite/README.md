#NetSuite transfer updates to NetSuite
- This integration is responsible for receiving events from NewStore regarding ASNs and Transfer Orders and send the updates to the records in NetSuite.

##DC to Store Transfer
For every completed receiving session with ASN NewStore will send the event inventory_transaction.items_received to this integration. This integration will then create an ItemReceipt in Netsuite against the ItemFulfilment that originated the ASN. Once all items are received, the ASN is marked as closed automatically in NewStore. This integration make updates accordingly in NetSuite.

###Inventory Transfer to NetSuite
Receive NewStore events inventory_transaction.items_received and creates item receipts for them on NetSuite.

##Store to DC and Store to Store Transfer
- Common case: NewStore integration will need to create an ItemFulfilment in Netsuite against the Transfer Order created
- Logic only for Store to Store Transfer: When the store receiving is completed in Store Y, NewStore integration will need to create ItemReceipts in Netsuite against the ItemFulfilment.

###Fulfill Transfer Orders in NetSuite
Integration layer to create ItemFulfillment records when a transfer order is marked shipped in NewStore which generates an ASN in NewStore by NewStore.

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
    "item_receipt_custom_form": "",
    "inventory_adjustment_custom_form": "",
    "inventory_adjustment_account_id": "",
    "currency_usd_internal_id": "",
    "currency_cad_internal_id": "",
    "currency_gbp_internal_id": "",
    "currency_eur_internal_id": "",
    "subsidiary_us_internal_id": "",
    "subsidiary_ca_internal_id": "",
    "subsidiary_uk_internal_id": ""
}
```
