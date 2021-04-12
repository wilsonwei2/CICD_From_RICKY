# Inventory push to Shopify
 - This stack is responsible for getting inventory information from NewStore and updating the inventory on Shopify and it's composed by 5 lambdas.

## Lambda functions
 - inventory_create_export_job: Here's where everything begins. It is triggered by a CloudWatch event everyday and is responsible for creating the inventory export job at NewStore. At the end it calls the inventory_push_to_queue lambda.
 - inventory_push_to_queue: After the export job is created by the inventory_create_export_job lambda it calls this lambda that is responsible for pushing information into a queue. At the end it calls the inventory_push_to_shopify lambda.
 - inventory_push_to_shopify: This lambda is called by the inventory_push_to_queue and is responsible for reading the queue and pushing the information of inventory to Shopify.
 - sync_shopify_products: This is responsible for creating a map of products between Shopify and NewStore. It is triggered by inventory_push_to_shopify or by in_store_order_update_inventory_at_shopify.
 - in_store_order_update_inventory_at_shopify: This one receives order.created events from NewStore and update the availability on Shopify.
 - set_inventory_locations: This lambda is triggered by an SQS event and it processes the QUEUE that receives messages from the product import lambda. This lambda is responsible for setting inventory ATP 0 on Shopify for all the locations configured in the parameter store path `/frankandoak/<STAGE>/shopify/locations_id_list`

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
 - sync_shopify_products
    - "TENANT": Name of the tenant (e.g. frankandoak)
    - "STAGE": Letter that represents the stage being utilized (e.g. x for sandbox)
    - "S3_BUCKET_NAME": Name of the S3 bucket for the tenant. Utilized to save the product map file
    - "NAMESPACE_METAFIELDS": Namespace of the metafield on Shopify for the variants that save the SKU
    - "VARIANT_NS_SKU_METAFIELD_NAME": Name of the metafield that stores the SKU information on the variants in Shopify
 - in_store_order_update_inventory_at_shopify
    - "TENANT": Name of the tenant (e.g. frankandoak)
    - "STAGE": Letter that represents the stage being utilized (e.g. x for sandbox)
    - "S3_BUCKET_NAME": Name of the S3 bucket for the tenant. Utilized to save the product map file
- set_inventory_locations
    - "TENANT": Name of the tenant (e.g. frankandoak)
    - "STAGE": Letter that represents the stage being utilized (e.g. x for sandbox)
    - "SQS_NAME": Name of the SQS queue to be utilized to get the inventory information about products
    - "MESSAGE_COUNTER": Number of max messages to read in each execution
