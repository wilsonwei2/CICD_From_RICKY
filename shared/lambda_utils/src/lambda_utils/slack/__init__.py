
# slack client id: 5173193402.126682977377
# client secret: a267cd2a801b658466014b11192078a1
# curl -X POST --data-urlencode 'payload={"channel": "#integrations-log-x", "username": "integrations", "text": "Test message from Adidas Ingress.", "icon_emoji": ":ghost:"}' https://hooks.slack.com/services/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

import json
import requests

SLACK_URL = 'https://hooks.slack.com/services/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'
SLACK_USERNAME = 'integrations'


def send_to_slack(channel=None, text=None):
    if channel is None or text is None:
        return
    payload = {
        'channel': channel,
        'username': SLACK_USERNAME,
        'text': text
    }
    return requests.post(
        SLACK_URL,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data=json.dumps(payload)
    )
