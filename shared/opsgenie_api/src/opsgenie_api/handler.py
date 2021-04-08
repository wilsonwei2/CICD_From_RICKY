from enum import Enum

from opsgenie_api.wrapper import OpsgenieApi
from opsgenie_api.model import OpsgeniePriority

class AlertLevel(Enum):
     Critical = 1
     High = 2
     Moderate = 3
     Low = 4
     Informational = 5

class AlertHandler:

    def __init__(self, api: OpsgenieApi, level: AlertLevel):

        self.api = api
        self.level = level

    def build_alias(self, alert_type:str, entity_id:str):

        return self.api.build_alias(alert_type, entity_id)

    def get_alert(self, alias: str):

        return self.api.get_alert(alias)

    def close_alert_build_alias(self, alert_type:str, entity_id:str):

        alias = self.build_alias(alert_type, entity_id)
        return self.api.close_alert(alias)

    def close_alert(self, alias:str):

        return self.api.close_alert(alias)

    def publish_alert(self, alert_type:str, entity_id:str, message:str, description:str=None, level=AlertLevel.Moderate):

        if level.value > self.level.value:
            return None

        return self.api.publish_alert(alert_type, entity_id, message, description, OpsgeniePriority[level.name])
