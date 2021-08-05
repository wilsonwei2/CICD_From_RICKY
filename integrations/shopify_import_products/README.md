# Importing Shopify products

## Setup

Create an entry in AWS Systems Manager Params Store - `/frankandoak/[stage]/shopify`:

    {
      "shop": "***",
      "username": "***",
      "password": "***"
    }

Create an entry in AWS Systems Manager Params Store - `/frankandoak/[stage]/newstore`:

    {
      "host": "***",
      "username": "***",
      "password": "***"
    }

## Full import

Set the Lambda environment variable `is_full=true` and start run it.


## Debugging

You can change the `products_per_file` (default: '25000') environment variable to a lower number,
this will increase the number of files and import jobs, but will help if you need to download and
analyse a transformed file.

