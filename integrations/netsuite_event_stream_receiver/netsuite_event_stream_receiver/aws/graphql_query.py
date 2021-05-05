ORDER_VALIDATION_QUERY = """
query MyQuery($id: String!, $tenant: String!) {
  order(id: $id, tenant: $tenant) {
    externalId
    isHistorical
    }
}
"""