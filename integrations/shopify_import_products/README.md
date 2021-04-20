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
