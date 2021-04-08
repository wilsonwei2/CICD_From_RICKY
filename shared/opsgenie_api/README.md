# OpsGenie alerts Python connector
Library to use Opsgenie alerts in integration workflows.

# Usage
## Create alert handler

        alert_level = AlertLevel[lambda_parameters["alert_level"]]
        
        stage = "x" or "s" or "p"
        tenant = "ganni"
        opsgenie_token = "00000000-0000-0000-0000-000000000000"
        opsgenie_responders = [{"name":"ps_ganni", "type":"team"}]
        opsgenie_visible_to = [{"name":"ps_ganni", "type":"team"}]
        opsgenie_actions = ["triage"]

        opsgenie_context = OpsgenieContext(
        opsgenie_token,
        tenant,
        stage,
        opsgenie_responders,
        opsgenie_visible_to,
        opsgenie_actions,
        "NewStore Integrator",
        lambda_context)

        alert_handler = create_alert_handler(opsgenie_context, alert_level)
        
The following properties are used from lambda context:
- function_name
- function_version
- aws_request_id

The given alert level acts as threshold. That means a publish below this level is skipped.

## Publish an alert

        alert_type = "navision_sync_order_injector"
        order_id = "GAN0000001"
        message = f"Unable to inject order => {order_id}"
        description = str(ex)
        # Is fired
        case_alert_level = AlertLevel.High
        # Is skipped because of alert handler threshold AlertLevel.High
        case_alert_level = AlertLevel.Moderate
        response = alert_handler.publish_alert(alert_type, order_id, message, description, case_alert_level)

### Response data

Internally the alias is created from alert_type and entity_id. The response always contains the used purified alias, which must be used as identifier in all other functions.

The data field contains the original opsgenie response.

    {
        "alias": "navision_sync_order_injector_gan0000001",
        "data": {
            "result": "Request will be processed",
            "took": 0.008,
            "requestId": "87b43092-187c-4968-bda2-7b62b693cb96"
        }
    }

# Close an alert

Use the alias from publish_alert response or build an new valid alias via

        # alias = "navision_sync_order_injector_gan0000001"
        alias = alert_handler.build_alias("navision_sync_order_injector", "GAN0000001")
        response = alert_handler.close_alert(alias)

        # Shortener
        close_alert_build_alias("navision_sync_order_injector", "GAN0000001")



