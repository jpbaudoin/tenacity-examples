# Handling transient errors for web APIs and AWS calls in python

Nowadays, consuming external services via APIs or by using wapper libraries is pretty common.
In this context distinguish between temporal issues(throttling, service unavailable) and non-recoverable ones is important as we can establish a retry policy for the former and handle the latter.

We will explore how to handle these errors for two scenarios:
- HTTP request to an API using slack webhooks as an example
- Use an external service library using boto3

To implement the retries in our code, we will use the library *tenacity*.
All the code used can be found at: https://github.com/jpbaudoin/tenacity-examples

## About tenacity
Tenacity is a very useful library for implementing retries in your python functions.
One of the main attractive features of tenacity is that is not invasive to your code and the implementation of retries can be easily done just by using decorators.

You can see several handy examples on the documentation: https://tenacity.readthedocs.io/en/latest/

Additionally, tenacity is an active project:
- 53 contributors.
- Several releases per year.
- Currently on version 7, released this year.

## Case #1: Posting messages to Slack webhook

Below a simple code snippet to post a basic message on a slack channel via a webhook.
```python
import json
import requests
from config import slack_cfg

## Prepare the slack message
msg = dict(
    icon_emoji=":smile:",
    username="PythonProcess",
    text="This is a simple text"
)

def send_msg_slack(web_hook_url, channel, msg):
    msg["channel"] = "#{channel}".format(channel=channel)
    print(msg)
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
```

The results of executing this are shown below:
```log
python3 slack_simple_rq.py

Testing Webhook
ok

Force failure using a non-existing channel
404 Client Error: Not Found for url: https://hooks.slack.com/services/my-slack-webhook

Force failure erro 5XX mock
500 Server Error: Server Error for url: http://b4d.mocklab.io/err500
```

We can observe that all requests worked as designed:
- The first one was successful, the expected result in normal conditions
- The second one returned an error 404 indicating the missing channel
- Finally, the third one returned a 500 error as defined in the stub used.

### Add retries - simple aproach
Here we will define a retrying policy and apply it to the *send_msg_slack* function.
The policy shall:
- Use exponential back-off
- Try 4 times including the initial posting
- Log a message on each retry

Below the changes to implement on the previous code, 

```python
import json
import requests
from config import slack_cfg
from tenacity import retry, stop_after_attempt, before_log, wait_exponential
import logging

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
logger = logging.getLogger(__name__)
...

@retry(stop=stop_after_attempt(4), before=before_log(logger, logging.DEBUG), wait=wait_exponential(multiplier=1, min=4, max=10))
def send_msg_slack(web_hook_url, channel, msg):
    ...
```

If we execute the code we get:

```log
python3 slack_simple_rq_retries.py

Testing Webhook
DEBUG:__main__:Starting call to '__main__.send_msg_slack', this is the 1st time calling it.
DEBUG:urllib3.connectionpool:Starting new HTTPS connection (1): hooks.slack.com:443
DEBUG:urllib3.connectionpool:https://hooks.slack.com:443 "POST /services/my-slack-webhook HTTP/1.1" 200 22
ok

Force failure using a non-existing channel
DEBUG:__main__:Starting call to '__main__.send_msg_slack', this is the 1st time calling it.
DEBUG:urllib3.connectionpool:Starting new HTTPS connection (1): hooks.slack.com:443
DEBUG:urllib3.connectionpool:https://hooks.slack.com:443 "POST /services/my-slack-webhook HTTP/1.1" 404 None
DEBUG:__main__:Starting call to '__main__.send_msg_slack', this is the 2nd time calling it.
DEBUG:urllib3.connectionpool:Starting new HTTPS connection (1): hooks.slack.com:443
DEBUG:urllib3.connectionpool:https://hooks.slack.com:443 "POST /services/my-slack-webhook HTTP/1.1" 404 None
DEBUG:__main__:Starting call to '__main__.send_msg_slack', this is the 3rd time calling it.
DEBUG:urllib3.connectionpool:Starting new HTTPS connection (1): hooks.slack.com:443
DEBUG:urllib3.connectionpool:https://hooks.slack.com:443 "POST /services/my-slack-webhook HTTP/1.1" 404 None
DEBUG:__main__:Starting call to '__main__.send_msg_slack', this is the 4th time calling it.
DEBUG:urllib3.connectionpool:Starting new HTTPS connection (1): hooks.slack.com:443
DEBUG:urllib3.connectionpool:https://hooks.slack.com:443 "POST /services/my-slack-webhook HTTP/1.1" 404 None
RetryError[<Future at 0x10621d1f0 state=finished raised HTTPError>]

Force failure erro 5XX mock
DEBUG:__main__:Starting call to '__main__.send_msg_slack', this is the 1st time calling it.
DEBUG:urllib3.connectionpool:Starting new HTTP connection (1): b4d.mocklab.io:80
DEBUG:urllib3.connectionpool:http://XXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
DEBUG:__main__:Starting call to '__main__.send_msg_slack', this is the 2nd time calling it.
DEBUG:urllib3.connectionpool:Starting new HTTP connection (1): b4d.mocklab.io:80
DEBUG:urllib3.connectionpool:http://XXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
DEBUG:__main__:Starting call to '__main__.send_msg_slack', this is the 3rd time calling it.
DEBUG:urllib3.connectionpool:Starting new HTTP connection (1): b4d.mocklab.io:80
DEBUG:urllib3.connectionpool:http://XXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
DEBUG:__main__:Starting call to '__main__.send_msg_slack', this is the 4th time calling it.
DEBUG:urllib3.connectionpool:Starting new HTTP connection (1): b4d.mocklab.io:80
DEBUG:urllib3.connectionpool:http://XXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
RetryError[<Future at 0x1062bc4f0 state=finished raised HTTPError>]
```

In terms of results from the calls we can see that the same behavior occurred, but now we can also appreciate the retries for the error cases, 4 attempts for the error 404, and the same for the 500 error.

At this point, it is important to note that retries for an error 404 in most cases are a waste of resources as the situation is mostly an error on the side of the client.

So if we take a look at the Slack documentation for errors and rate limits we can take the following actions regarding the status obtained on each request:
- Status 429: Retry
- Status 4XX: Don't retry
- Status 500: Retry

Slack documentation:
- https://api.slack.com/messaging/webhooks#handling_errors
- https://api.slack.com/changelog/2016-05-17-changes-to-errors-for-incoming-webhooks
- https://api.slack.com/docs/rate-limits#rate-limits__responding-to-rate-limiting-conditions


The changes for improvement were done at the *send_msg_slack* function and on the retry policy config as shown below:

```python
@retry(stop=stop_after_attempt(4), before=before_log(logger, logging.DEBUG),
       wait=wait_exponential(multiplier=1, min=4, max=10),
       retry=retry_if_exception_type(SendMsgError))
def send_msg_slack(web_hook_url, channel, msg):
    msg["channel"] = "#{channel}".format(channel=channel)
    msg_rq = requests.post(url=web_hook_url, json=msg, headers={
        'Content-Type': 'application/json'})
    response = msg_rq.text

    if msg_rq.status_code == 200:
        return response
    elif  msg_rq.status_code == 429 or  msg_rq.status_code >= 500:
        # Retry
        raise SendMsgError("{msg} - {status}".format(msg=response, status= msg_rq.status_code))
    else:
        # Fail with no retries
        msg_rq.raise_for_status()
    return response
````