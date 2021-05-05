import logging
from typing import Optional

from newstore_common.aws.dynamo_db import DynamoStore

LOGGER = logging.getLogger(__name__)


class ItemIdsStore(DynamoStore):

    def update_item(self, newstore_sku: str, netsuite_internalid, ttl: Optional[int]):
        response = self.get_table().update_item(
            Key={
                'newstore_sku': newstore_sku
            },
            UpdateExpression="set netsuite_id=:netsuite_id, #TimeToLive=:TimeToLive",
            ExpressionAttributeValues={
                ':netsuite_id': netsuite_internalid,
                ':TimeToLive': ttl
            },
            ExpressionAttributeNames={
                "#TimeToLive": "ttl"
            },
            ReturnValues="NONE"
        )
        return response
