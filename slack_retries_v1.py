
import json
import requests
from config import slack_cfg
from tenacity import retry, stop_after_attempt, before_log, wait_exponential
import logging
import sys

# Setting up the logger to use on the retry config
logging.basicConfig(format='%(asctime)s :: %(levelname)s :: %(message)s',
                    stream=sys.stderr, level=logging.DEBUG)
logger = logging.getLogger(__name__)



## Prepare the slack message
msg = dict(
    icon_emoji=":smile:",
    username="PythonProcess",
    text="This is a simple text"
)

# Decorator with the retry policy
@retry(stop=stop_after_attempt(4), before=before_log(logger, logging.DEBUG),
       wait=wait_exponential(multiplier=1, min=0, max=10))
def send_msg_slack(web_hook_url, channel, msg):
    msg["channel"] = "#{channel}".format(channel=channel)
    msg_rq = requests.post(url=web_hook_url, json=msg, headers={
        'Content-Type': 'application/json'})
    response = msg_rq.text
    msg_rq.raise_for_status()
    return response


# Test the webhook
print("\nTesting Webhook")
web_hook_url = slack_cfg['slack_webhook']['url']
web_hook_ch = slack_cfg['slack_webhook']['channel']

response = send_msg_slack(web_hook_url, web_hook_ch, msg)
print(response)

# Force failure using a non-existing channel
print("\nForce failure using a non-existing channel")
web_hook_url = slack_cfg['slack_webhook']['url']
web_hook_ch = "#NA"

try:
    response = send_msg_slack(web_hook_url, web_hook_ch, msg)
    print(response)
except Exception as err:
    print(str(err))


# Run test mocking error 500
print("\nForce failure erro 5XX mock")
web_hook_url = slack_cfg['slack_mock5XX']
web_hook_ch = "#NA"

try:
    response = send_msg_slack(web_hook_url, web_hook_ch, msg)
    print(response)
except Exception as err:
    print(str(err))
