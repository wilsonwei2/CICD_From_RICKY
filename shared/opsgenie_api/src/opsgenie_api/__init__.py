from opsgenie_api.model import OpsgenieContext
from opsgenie_api.wrapper import OpsgenieApi
from opsgenie_api.handler import AlertHandler, AlertLevel

def create_alert_handler(opsgenie_context: OpsgenieContext, alert_level: AlertLevel):

    opsgenie_api = create_opsgenie_api(opsgenie_context)
    return AlertHandler(opsgenie_api, alert_level)

def create_opsgenie_api(opsgenie_context):

    return OpsgenieApi(opsgenie_context)