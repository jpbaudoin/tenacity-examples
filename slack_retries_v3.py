from datetime import datetime
from config import slack_cfg
from tenacity import retry, stop_after_attempt, before_log, wait_exponential, retry_if_exception_type
import time
import requests
import json
import sys

import logging

logging.basicConfig(format='%(asctime)s :: %(levelname)s :: %(message)s',
                    stream=sys.stderr, level=logging.DEBUG)
logger = logging.getLogger(__name__)

def custom_wait(retry_state):
    func_object = retry_state.args[0]               # Get the class object
    func_name = retry_state.fn.__name__             # Get the retried function name
    wait = func_object.wait.get(func_name, None)    # Get the wait time form the wait dict on the object
    if wait is None:
        # No wait time then default to the default retry policy
        return default_wait(retry_state)
    else:
        # Clean the wait time and retun the wait value
        func_object.wait[func_name] = None
        return wait

def default_wait(retry_state):
    return wait_exponential(multiplier=1, min=0, max=10)(retry_state)
    
class SendMsgError(Exception):
    pass

## Prepare the slack message
msg = dict(
    icon_emoji=":smile:",
    username="PythonProcess",
    text="This is a simple text"
)

# Slack messages posting code refactored as a class
class SlackPub():
    def __init__(self, whook_url, channel):
        self.whook_url = whook_url
        self.channel = channel
        self.wait = dict()                  # A dict to store the wait times
        self.wait['send_msg_slack'] = None


    @retry(stop=stop_after_attempt(4), before=before_log(logger, logging.DEBUG),
           wait=custom_wait,
           retry=retry_if_exception_type(SendMsgError))
    def send_msg_slack(self, msg):
        msg["channel"] = "#{channel}".format(channel=self.channel)
        msg_rq = requests.post(url=self.whook_url, json=msg, headers={
            'Content-Type': 'application/json'})
        response = msg_rq.text

        if msg_rq.status_code == 200:
            return response
        elif msg_rq.status_code == 429:
            # Retry
            retry_after = msg_rq.headers.get("Retry-After", None)
            if retry_after is not None:
                self.wait['send_msg_slack'] = int(retry_after)
            raise SendMsgError("{msg} - {status}".format(msg=response, status= msg_rq.status_code))
        elif msg_rq.status_code >= 500:
            # Retry
            raise SendMsgError("{msg} - {status}".format(msg=response, status= msg_rq.status_code))
        else:
            # Fail with no retries
            msg_rq.raise_for_status()
        return response


# Test the webhook
print("\nTesting Webhook")
web_hook_url = slack_cfg['slack_webhook']['url']
web_hook_ch = slack_cfg['slack_webhook']['channel']
slack_cli = SlackPub(web_hook_url, web_hook_ch)

response = slack_cli.send_msg_slack(msg)
print(response)

# Force failure using a non-existing channel
print("\nForce failure using a non-existing channel")
web_hook_url = slack_cfg['slack_webhook']['url']
web_hook_ch = "#NA"
slack_cli = SlackPub(web_hook_url, web_hook_ch)

try:
    response = slack_cli.send_msg_slack(msg)
    print(response)
except Exception as err:
    print(str(err))


# Run test mocking error 500
print("\nForce failure erro 5XX mock")
web_hook_url = slack_cfg['slack_mock5XX']
web_hook_ch = "#NA"
slack_cli = SlackPub(web_hook_url, web_hook_ch)

try:
    response = slack_cli.send_msg_slack(msg)
    print(response)
except Exception as err:
    print(str(err))

# Run test mocking error 429
print("\nForce failure erro 429 mock")
web_hook_url = slack_cfg['slack_mock429']
web_hook_ch = "#NA"
slack_cli = SlackPub(web_hook_url, web_hook_ch)

try:
    response = slack_cli.send_msg_slack(msg)
    print(response)
except Exception as err:
    print(str(err))