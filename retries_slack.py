from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_fixed, wait_chain
import time
import requests
import json
import sys

import logging
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
logger = logging.getLogger(__name__)

TOO_MANY_CALLS = 429


class SendMsgError(Exception):
    def __init__(self, message, state):
        self.message = message
        self.state = state

    def __str__(self):
        return self.message


def default_wait(retry_state):
    return wait_chain(*[wait_fixed(1) for i in range(2)] +
                      [wait_fixed(3) for i in range(2)] +
                      [wait_fixed(6)])(retry_state)


def custom_wait(retry_state):
    #import ipdb; ipdb.set_trace()
    func_object = retry_state.args[0]
    func_name = retry_state.fn.__name__
    wait = func_object.wait.get(func_name, None)
    if wait is None:
        return default_wait(retry_state)
    else:
        func_object.wait[func_name] = None
        return wait


def retry_options(function):
    function = retry(reraise=True,
                     stop=stop_after_attempt(4),
                     wait=custom_wait)(function)
    return function


def run_test(test_func):
    start = False
    while True:
        sec_unit = datetime.now().second % 5
        # print(sec_unit)
        if start:
            print("\n##### Lauching function #####")
            test_func()
            time.sleep(1)
            start = False
        else:
            start = sec_unit == 0
            #import ipdb
            # ipdb.set_trace()


class SlackPub():
    def __init__(self):
        self.wait = dict()
        self.wait['send_msg_slack'] = None

    def prepare_msg(self):
        inner_params = dict(
            channel="#" + "learning",
            icon_emoji=":screm_cat:",
            username="username"
        )
        block = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Budget Performance"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "This is the text",
                }
            }
        ]
        inner_params['blocks'] = block
        return inner_params

    @retry_options
    def send_msg_slack(self, web_hook_url):

        msg = self.prepare_msg()
        msg_rq = requests.post(url=web_hook_url, json=msg, headers={
            'Content-Type': 'application/json'})

        response = msg_rq.text
        result = {
            "success": True,
            "response": response,
            "err_msg": "",
            "destination": "destination"
        }

        if msg_rq.status_code != 200:

            err_msg = "{url}: {status} - {reason}".format(
                url=web_hook_url, status=msg_rq.status_code, reason=msg_rq.reason)
            result['success'] = False
            result['err_msg'] = err_msg
            logger.info(err_msg)
            if msg_rq.status_code == TOO_MANY_CALLS:
                # Get the waiting time, see: https://api.slack.com/docs/rate-limits
                retry_after = msg_rq.headers.get("Retry-After", None)
                #import ipdb; ipdb.set_trace()
                if retry_after is None:
                    raise SendMsgError(err_msg, result)
                else:
                    self.wait['send_msg_slack'] = int(retry_after)
                    raise SendMsgError(err_msg, result)
            if msg_rq.status_code >= 500:
                raise SendMsgError(err_msg, result)
        return result


slack_cli = SlackPub()

with open('config.json') as json_file:
    config = json.load(json_file)

for cfg, url in config.items():
    print("\n\nRuning test: {cfg}".format(cfg=cfg))
    try:
        rst = slack_cli.send_msg_slack(url)
    except:
        print("Failure")
        pass
    print(slack_cli.send_msg_slack.retry.statistics)

