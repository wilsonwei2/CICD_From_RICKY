# Inventory push to Shopify

This stack is responsible for getting inventory information from NewStore and updating the inventory on Shopify and it's composed by 3 lambdas.

# Setup

Create an entry in AWS Systems Manager Params Store - `/frankandoak/[stage]/shopify/locations_map_info`:

    {
      "61470441628": "STANST",
      [...]
    }

This should map all the location IDs from Shopify to the location IDs in NewStore.


## Lambda functions
 - inventory_create_export_job: Here's where everything begins. It is triggered by a CloudWatch event everyday and is responsible for creating the inventory export job at NewStore. At the end it calls the inventory_push_to_queue lambda.
 - inventory_push_to_queue: After the export job is created by the inventory_create_export_job lambda it calls this lambda that is responsible for pushing information into a queue. At the end it calls the inventory_push_to_shopify lambda.
 - inventory_push_to_shopify: This lambda is called by the inventory_push_to_queue and is responsible for reading the queue and pushing the information of inventory to Shopify.

 ## Environment variables
 - inventory_create_export_job
    - "TENANT": Name of the tenant (e.g. frankandoak)
    - "STAGE": Letter that represents the stage being utilized (e.g. x for sandbox)
    - "S3_BUCKET_NAME": Name of the S3 bucket for the tenant. Utilized to save the export availability file
    - "FORCE_CHECKING_FOR_JOB": Flag to force checking of job
    - "PUSH_TO_QUEUE_LAMBDA_NAME": Name of the lambda inventory_push_to_queue on AWS
 - inventory_push_to_queue
    - "TENANT": Name of the tenant (e.g. frankandoak)
    - "STAGE": Letter that represents the stage being utilized (e.g. x for sandbox)
    - "S3_BUCKET_NAME": Name of the S3 bucket for the tenant. Utilized to save the export availability file
    - "SQS_NAME": Name of the SQS queue to be utilized to save the inventory information
    - "VARIANTS_PER_MESSAGE": Max number of variants per message to be put on the SQS queue
    - "PUSH_TO_SHOPIFY_LAMBDA_NAME": Name of the lambda inventory_push_to_shopify on AWS
    - "FORCE_EXPORT_UPDATE": Flag to force export update
 - inventory_push_to_shopify
    - "TENANT": Name of the tenant (e.g. frankandoak)
    - "STAGE": Letter that represents the stage being utilized (e.g. x for sandbox)
    - "SQS_NAME": Name of the SQS queue to be utilized to save the inventory information
    - "TRIGGER_NAME": Name of the CloudWatch trigger that is responsible for triggering this lambda
    - "SYNC_SHOPIFY_PRODUCTS_LAMBDA_NAME": Name of the lambda sync_shopify_products on AWS
