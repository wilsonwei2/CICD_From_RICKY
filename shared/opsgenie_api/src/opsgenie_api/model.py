from enum import Enum

class OpsgeniePriority(Enum):
     Critical = "P1"
     High = "P2"
     Moderate = "P3"
     Low = "P4"
     Informational = "P5"

class OpsgenieContext:
    def __init__(self,
        api_key: str,
        tenant: str,
        stage: str,
        responders: {},
        visible_to: {},
        actions: [],
        integrator_name: str,
        event_context):

        self.api_key = api_key
        self.tenant = tenant
        self.stage = stage
        self.responders = responders
        self.visible_to = visible_to
        self.actions = actions
        self.integrator_name = integrator_name
        self.function_version = event_context.function_version
        self.function_name = event_context.function_name
        self.aws_request_id = event_context.aws_request_id

    def get_source(self):
        return f"Integrator Name: {self.integrator_name}; Lambda Name: {self.function_name}; Lambda Version: {self.function_version}"

    def get_stage(self):
        return self.stage

    def get_tenant(self):
        return self.tenant

    def get_api_key(self):
        return self.api_key

    def get_responders(self):
        return self.responders

    def get_visible_to(self):
        return self.visible_to

    def get_actions(self):
        return self.actions

    def get_aws_request_id(self):
        return self.aws_request_id

    def get_function_name(self):
        return self.function_name

    def get_function_version(self):
        return self.function_version

    def get_integrator_name(self):
        return self.integrator_name
