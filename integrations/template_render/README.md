# Marine Layer Template Render
 - Renders the chosen template (receipts, documents etc.) and uploads to S3 for an order. The link to the S3 file will be returned by the Lambda.

# This endpoint receives a request payload of the following structure:
```json
{
    "content_type": "pdf",
    "template": "gift_receipt",
    "style": "",
    "data": {
        "external_id": "345123",
        "order_number": "345123",
        "flat_items": [
            {
                "product_name": "Brie Size 2 / Regular Fit / Light Blue",
                "product_id": "34003BluReg2",
                "external_identifier": {
                    "sku": "34003BluReg2"
                },
                "product_attributes": {
                    "variation_size_value": "Size 2",
                    "variation_color_value": "Light Blue"
                }
            }
        ],
        "created_at": "2019-10-22T19:22:28.89146Z",
        "store_address": {
            "address_line_1": "11111",
            "address_line_2": "22222",
            "city": "Pittsburgh",
            "state": "PA",
            "zip_code": "33333",
            "country_code": "US"
        },
        "timezone": "America/New_York"
    }
}
```

## Environment variables for Lambda function template-render
- "S3_BUCKET": S3 bucket where function will be deployed (in deployments folder) and template will be uploaded (documents folder)
- "S3_KEY_PREFIX": Use default -> "documents"
- "VERSION": Use default -> "v0"
- "URL_API": API endpoint for tenant

## Variables to specify when using make command
-(REQUIRED) DEPLOYMENT_ACCOUNT_NUMBER: Account number of AWS account attempting to make
-(OPTIONAL) UrlApi: API endpoint for tenant (fed into Lambda), default -> aninebing.p.newstore.net (production)
-(OPTIONAL) NEWSTORE_TENANT = Name of tenant, default -> aninebing (production)
-(OPTIONAL) NEWSTORE_STAGE = Letter designating stage, default -> p (production)
-(OPTIONAL) CLOUDFORMATION_STACK_NAME = Name of stack to be modified, default -> aninebing-p-template-render (production)

