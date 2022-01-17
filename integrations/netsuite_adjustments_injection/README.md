#NetSuite Adjustments Injection
- Process events of type `inventory_transaction.adjustment_created` received by the `netsuite_event_stream_receiver` integration via SQS queue and creates InventoryTransfer records in NetSuite for it.

##Configuration
- There are configurations that need to be set in the AWS Parameter Store for this integration to work properly, they are listed bellow.

1. Path /<tenant>/<stage>/netsuite/newstore_to_netsuite_locations
```
{
	"store_id": { # Store ID in NewStore
		"id": "000", # Location ID in NetSuite for this Store
		"id_damage": "000", # Damaged Location ID in NetSuite for this Store
		"ff_node_id": "XXX" # Fulfillment node ID in NewStore for this Store
	}
}
```

2. Path /<tenant>/<stage>/netsuite # TODO Verify if FAO uses all the bellow keys and if not remove them from codes
```
{
	"currency_usd_internal_id": "",
	"currency_cad_internal_id": "",
	"currency_gbp_internal_id": "",
	"currency_eur_internal_id": "",
	"subsidiary_us_internal_id": "",
	"subsidiary_ca_internal_id": "",
	"subsidiary_uk_internal_id": "", # Not utilized/needed for FAO
	"us_retail_write_off": "", # Not utilized/needed for FAO
	"us_warehouse_write_off": "", # Not utilized/needed for FAO
	"ca_retail_write_off": "", # Not utilized/needed for FAO
	"ca_warehouse_write_off": "", # Not utilized/needed for FAO
	"uk_retail_write_off": "", # Not utilized/needed for FAO
	"uk_warehouse_write_off": "" # Not utilized/needed for FAO
}
```

3. Path /<tenant>/<stage>/newstore
```
{
	"host": "",
	"username": "",
	"password": ""
}
```
