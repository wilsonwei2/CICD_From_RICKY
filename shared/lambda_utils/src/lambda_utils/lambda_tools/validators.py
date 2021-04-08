import logging


logger = logging.getLogger(__name__)

def event_validator(event, global_vars):
    """
    Validate for repeated event, if new add the value to lambda vars
    :param event: event from aws
    :param global_vars: global vars of the function
    :return: nothing
    """
    sequenceEventId = event['Records'][0]['s3']['object'].get('sequencer', None)
    lastEventId = global_vars.get('last_event_id', None)

    if lastEventId is not None and sequenceEventId is not None:
        if len(lastEventId) > len(sequenceEventId):
            sequenceEventId = sequenceEventId.ljust(len(lastEventId) , '0')
        elif len(sequenceEventId) > len(lastEventId):
            lastEventId = lastEventId.ljust(len(sequenceEventId) , '0')

        if lastEventId is None or int(sequenceEventId) > int(lastEventId):
            return sequenceEventId
        elif lastEventId == sequenceEventId:
            raise Exception("Event with id %s consumed or in process... Discarding " % lastEventId)

    return None