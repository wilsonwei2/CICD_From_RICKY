START_BULK_OPERATIONS = '''
    mutation {
        bulkOperationRunQuery(
            query: """
                {
                    products {
                        edges {
                            node {
                                id
                                status
                                vendor
                                title
                                bodyHtml
                                tags
                                createdAt
                                updatedAt
                                publishedAt
                                handle
                                variants {
                                    edges {
                                        node {
                                            id
                                            sku
                                            weightUnit
                                            weight
                                            taxCode
                                            barcode
                                            createdAt
                                            updatedAt
                                            inventoryManagement
                                            inventoryPolicy
                                            fulfillmentService {
                                                handle
                                            }
                                            image {
                                                id
                                                altText
                                                originalSrc
                                            }
                                            inventoryItem {
                                                id
                                                harmonizedSystemCode
                                                countryCodeOfOrigin
                                            }
                                            selectedOptions {
                                                name
                                                value
                                            }
                                        }
                                    }
                                }
                                options {
                                    id
                                    position
                                    name
                                    values
                                }
                                images {
                                    edges {
                                        node {
                                            id
                                            altText
                                            originalSrc
                                        }
                                    }
                                }
                                metafields(namespace: "product") {
                                    edges {
                                        node {
                                            namespace
                                            id
                                            key
                                            value
                                        }
                                    }
                                }
                                translations(locale: "fr") {
                                    key
                                    value
                                }
                            }
                        }
                    }
                }
            """
        ) {
            bulkOperation {
                id
                status
            }
            userErrors {
                field
                message
            }
        }
    }
'''

POLL_OPERATION_STATUS = '''
    query {
        currentBulkOperation {
            id
            status
            errorCode
            url
        }
    }
'''
