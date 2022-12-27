# Shopify Import Order

## Setup

Create an entry in AWS Systems Manager Params Store - `/frankandoak/[stage]/shopify`:

    {
      "shop": "***",
      "username": "***",
      "password": "***",
      "shared_secret": "***"
    }

Create an entry in AWS Systems Manager Params Store - `/frankandoak/x/shopify/service_level`:

    {
      "default": "...",
      [...]
    }

Create an entry in AWS Systems Manager Params Store - `/frankandoak/[stage]/newstore`:

    {
      "host": "***",
      "username": "***",
      "password": "***"
    }

Setup **Shipping** in NewStore Omnichannel Manager.

Setup `ORDER_IMPORT_API` in lambdas:

* `frankandoak-shopify-sync-order-webhooks`
* `frankandoak-shopify-order-sync-newstore`

to `https://{URL}.com/{STAGE}` to match the API Gateway Endpoint from `frankandoak-receive-shopify-order`

## Order Level Discount Proration

First, a **POST** (Shopify makes this a POST, but no changes are made) to `admin/orders/{ORDER_ID}/refunds/calculate.json` is made and the response is transformed to be a `dict` keyed on the line item ids. Like such:

```javascript
{
  "533124710440": {
    "quantity": 1,
    "line_item_id": 533124710440,
    "price": "200.00",
    "subtotal": "121.51",
    "total_tax": "10.78",
    "discounted_price": "200.00",
    "discounted_total_price": "200.00",
    "total_cart_discount_amount": "78.49"
  },
  "533124775976": {
    "quantity": 1,
    "line_item_id": 533124775976,
    "price": "85.00",
    "subtotal": "51.64",
    "total_tax": "4.59",
    "discounted_price": "85.00",
    "discounted_total_price": "85.00",
    "total_cart_discount_amount": "33.36"
  }
}
```

From this, we're most concerned with the `"total_cart_discount_amount"` which gives us the prorated discount per line item. From there, we can map the value into the corresponding `item_order_discount_info`'s `price_adjustment` as long as the quanity is `1`. If it's greater than `1`, we must split it across that many line items, ensuring that there are no fractional cents as a result.

For example, if had a discount of 177.46 and quanity of 4, we'd have two line items with a cost of 44.36 and two with a cost of 44.37, summing to the original 177.46.


## Environment newstore
  - tenant = 'frankandoak-staging'
  - username = manual definition
  - password = manual definition
  - host = `https://frankandoak-staging.p.newstore.net` (default)
