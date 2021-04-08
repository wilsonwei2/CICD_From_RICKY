import boto3
import logging

logger = logging.getLogger(__name__)


class EventsHandler:
    def __init__(self, profile_name=None):
        """
        Construct events wrapper obj
        """
        self.session = boto3.Session(profile_name=profile_name)
        self.client = self.session.client('events')

    def update_trigger(self, trigger_name, schedule_expression, is_enabled):
        """
        Udate trigger
        :param trigger_name:
        :param schedule_expression:
        :param is_enabled:
        :return response: RuleArn
        """
        response = None
        if is_enabled:
            enabled = 'ENABLED'
        else:
            enabled = 'DISABLED'
        try:
            response = self.client.put_rule(
                Name=trigger_name,
                ScheduleExpression=schedule_expression,
                State=enabled
            )
        except Exception as ex:
            logger.exception(ex)

        return response
