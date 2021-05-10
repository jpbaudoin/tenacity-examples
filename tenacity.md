# Handling transient errors for web APIs in python

Nowadays, consuming external services via APIs or by using wapper libraries is pretty common.
In this context distinguish between temporal issues(throttling, service unavailable) and non-recoverable ones is important as we can establish a retry policy for the former and handle the latter.

We will explore how to handle these errors for HTTP requests using calls to slack webhooks API as an example.

To implement the retries we will use the python library [*tenacity*](https://github.com/jd/tenacity).

All the code used can be found at: https://github.com/jpbaudoin/tenacity-examples

## About tenacity
Tenacity is a very useful library for implementing retries in your python functions.
One of the main attractive features of tenacity is that is not invasive to your code and the implementation of retries can be easily done just by using decorators.

You can see several handy examples on the documentation: https://tenacity.readthedocs.io/en/latest/

Additionally, tenacity is an active project:
- 53 contributors.
- Several releases per year.
- Currently on version 7, released this year.

## Case: Posting messages to Slack webhook

Below a simple code snippet to post a basic message on a slack channel via a webhook.

[slack_simple_rq.py](./slack_simple_rq.py):
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

The result of executing the code is shown below:
```log
python3 slack_simple_rq.py

Testing Webhook
ok

Force failure using a non-existing channel
404 Client Error: Not Found for url: https://hooks.slack.com/services/my-slack-webhook

Force failure erro 5XX mock
500 Server Error: Server Error for url: http://XXXXX.mocklab.io/err500
```

We can observe that all requests worked as designed:
- The first one was successful, the expected result in normal conditions
- The second one returned an error 404 indicating the missing channel
- Finally, the third one returned a 500 error as defined in the stub used.

### Add retries - dummy aproach

The "simplest" retry mechanism is to include our code within a loop and control the retries and establish a sleep time before each call. Below a sample code with this approach:

[slack_retries_v0.py](./slack_retries_v0.py)
```python

import json
import requests
from config import slack_cfg
import logging
import time
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

TOTAL_ATTEMPS = 4
SLEEP = 1

def send_msg_slack(web_hook_url, channel, msg):
    attemp = 1
    while attemp <= TOTAL_ATTEMPS:
        logger.debug("Message attepmt: {attemp}".format(attemp=attemp))
        msg["channel"] = "#{channel}".format(channel=channel)
        msg_rq = requests.post(url=web_hook_url, json=msg, headers={
            'Content-Type': 'application/json'})
        response = msg_rq.text
        try:
            msg_rq.raise_for_status()
        except:
            attemp += 1
            time.sleep(SLEEP)
        else:
            return response
    # All retries failed
    # Raise last error
    msg_rq.raise_for_status()


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

This code acomplishes what we wanted as we can see on the following results:
```log
python3 slack_retries_v0.py 

Testing Webhook
2021-05-08 21:08:03,652 :: DEBUG :: Message attepmt: 1
2021-05-08 21:08:03,764 :: DEBUG :: Starting new HTTPS connection (1): hooks.slack.com:443
2021-05-08 21:08:04,268 :: DEBUG :: https://hooks.slack.com:443 "POST /services/XXXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX HTTP/1.1" 200 22
ok

Force failure using a non-existing channel
2021-05-08 21:08:04,272 :: DEBUG :: Message attepmt: 1
2021-05-08 21:08:04,276 :: DEBUG :: Starting new HTTPS connection (1): hooks.slack.com:443
2021-05-08 21:08:04,842 :: DEBUG :: https://hooks.slack.com:443 "POST /services/XXXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX HTTP/1.1" 404 None
2021-05-08 21:08:05,846 :: DEBUG :: Message attepmt: 2
2021-05-08 21:08:05,848 :: DEBUG :: Starting new HTTPS connection (1): hooks.slack.com:443
2021-05-08 21:08:06,378 :: DEBUG :: https://hooks.slack.com:443 "POST /services/XXXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX HTTP/1.1" 404 None
2021-05-08 21:08:07,380 :: DEBUG :: Message attepmt: 3
2021-05-08 21:08:07,383 :: DEBUG :: Starting new HTTPS connection (1): hooks.slack.com:443
2021-05-08 21:08:07,914 :: DEBUG :: https://hooks.slack.com:443 "POST /services/XXXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX HTTP/1.1" 404 None
2021-05-08 21:08:08,917 :: DEBUG :: Message attepmt: 4
2021-05-08 21:08:08,920 :: DEBUG :: Starting new HTTPS connection (1): hooks.slack.com:443
2021-05-08 21:08:09,395 :: DEBUG :: https://hooks.slack.com:443 "POST /services/XXXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX HTTP/1.1" 404 None
404 Client Error: Not Found for url: https://hooks.slack.com/services/XXXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

Force failure erro 5XX mock
2021-05-08 21:08:10,401 :: DEBUG :: Message attepmt: 1
2021-05-08 21:08:10,404 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 21:08:10,771 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
2021-05-08 21:08:11,773 :: DEBUG :: Message attepmt: 2
2021-05-08 21:08:11,776 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 21:08:12,138 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
2021-05-08 21:08:13,140 :: DEBUG :: Message attepmt: 3
2021-05-08 21:08:13,143 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 21:08:13,519 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
2021-05-08 21:08:14,524 :: DEBUG :: Message attepmt: 4
2021-05-08 21:08:14,526 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 21:08:14,900 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
500 Server Error: Server Error for url: http://XXXXX.mocklab.io/err500
```

There are some caveats(our humble opinion) with this approach that make it not desirable if we can use a library such as tenacity:
- It incorporates retrying logic into the logic of our code.
- The code is less readable and difficult to maintain.
- It is not flexible in terms of the definition of retries policies.

Let's see how we can use tenacity to implement this behavior in a cleaner and effective manner.

### Add retries - basic aproach
Here we will define a retrying policy and apply it to the *send_msg_slack* function.
The policy shall:
- Use exponential back-off
- Try 4 times including the initial posting
- Log a message on each retry

One of the mechanisims to implement a retry scheme in tenacity is by using a decorator that can be configured to suit our needs:
```python
@retry(stop=stop_after_attempt(4), 
       before=before_log(logger, logging.DEBUG), 
       wait=wait_exponential(multiplier=1, min=4, max=10))
````
Let's explain each of the settings:
- [stop](https://tenacity.readthedocs.io/en/latest/index.html#stopping): Defines the stop condition for retries, in this case at most 4 attempts.
- [before](https://tenacity.readthedocs.io/en/latest/index.html#before-and-after-retry-and-logging): Defines a function to run before each retry, in this case, we use tenacity's before_log function to send information about the retry to a logger.
- [wait](https://tenacity.readthedocs.io/en/latest/index.html#waiting-before-retrying): Defines the waiting period between retries, in our case we use the wait_exponential to implement an exponential backoff

Below we can see the code including the changes to implement this policy.

[slack_retries_v1.py](./slack_retries_v1.py)
```python
import json
import requests
from config import slack_cfg
from tenacity import retry, stop_after_attempt, before_log, wait_exponential
import logging
import sys

# Setting up the logger to use on the retry config
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
logger = logging.getLogger(__name__)


## Prepare the slack message
msg = dict(
    icon_emoji=":smile:",
    username="PythonProcess",
    text="This is a simple text"
)

# Decorator with the retry policy
@retry(stop=stop_after_attempt(4), before=before_log(logger, logging.DEBUG),
       wait=wait_exponential(multiplier=1, min=4, max=10))
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
```

If we execute the code we get:

```log
python3 slack_retries_v1.py

Testing Webhook
2021-05-08 21:12:04,415 :: DEBUG :: Starting call to '__main__.send_msg_slack', this is the 1st time calling it.
2021-05-08 21:12:04,522 :: DEBUG :: Starting new HTTPS connection (1): hooks.slack.com:443
2021-05-08 21:12:05,134 :: DEBUG :: https://hooks.slack.com:443 "POST /services/XXXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX HTTP/1.1" 200 22
ok

Force failure using a non-existing channel
2021-05-08 21:12:05,136 :: DEBUG :: Starting call to '__main__.send_msg_slack', this is the 1st time calling it.
2021-05-08 21:12:05,140 :: DEBUG :: Starting new HTTPS connection (1): hooks.slack.com:443
2021-05-08 21:12:05,617 :: DEBUG :: https://hooks.slack.com:443 "POST /services/XXXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX HTTP/1.1" 404 None
2021-05-08 21:12:06,622 :: DEBUG :: Starting call to '__main__.send_msg_slack', this is the 2nd time calling it.
2021-05-08 21:12:06,625 :: DEBUG :: Starting new HTTPS connection (1): hooks.slack.com:443
2021-05-08 21:12:07,439 :: DEBUG :: https://hooks.slack.com:443 "POST /services/XXXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX HTTP/1.1" 404 None
2021-05-08 21:12:09,443 :: DEBUG :: Starting call to '__main__.send_msg_slack', this is the 3rd time calling it.
2021-05-08 21:12:09,445 :: DEBUG :: Starting new HTTPS connection (1): hooks.slack.com:443
2021-05-08 21:12:09,914 :: DEBUG :: https://hooks.slack.com:443 "POST /services/XXXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX HTTP/1.1" 404 None
2021-05-08 21:12:13,920 :: DEBUG :: Starting call to '__main__.send_msg_slack', this is the 4th time calling it.
2021-05-08 21:12:13,923 :: DEBUG :: Starting new HTTPS connection (1): hooks.slack.com:443
2021-05-08 21:12:14,388 :: DEBUG :: https://hooks.slack.com:443 "POST /services/XXXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX HTTP/1.1" 404 None
RetryError[<Future at 0x101c4b1f0 state=finished raised HTTPError>]

Force failure erro 5XX mock
2021-05-08 21:12:14,391 :: DEBUG :: Starting call to '__main__.send_msg_slack', this is the 1st time calling it.
2021-05-08 21:12:14,964 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 21:12:15,334 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
2021-05-08 21:12:16,340 :: DEBUG :: Starting call to '__main__.send_msg_slack', this is the 2nd time calling it.
2021-05-08 21:12:16,343 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 21:12:16,746 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
2021-05-08 21:12:18,750 :: DEBUG :: Starting call to '__main__.send_msg_slack', this is the 3rd time calling it.
2021-05-08 21:12:18,753 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 21:12:19,122 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
2021-05-08 21:12:23,129 :: DEBUG :: Starting call to '__main__.send_msg_slack', this is the 4th time calling it.
2021-05-08 21:12:23,132 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 21:12:23,510 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
RetryError[<Future at 0x101cea4f0 state=finished raised HTTPError>]
```

In terms of results from the calls we can see that the same behavior occurred, but now we can also appreciate the retries for the error cases, 4 attempts for the error 404, and the same for the 500 error.

At this point, it is important to note that retries for an error 404 in most cases are a waste of resources as the situation is mostly an error on the side of the client.

### Do retries when needed

It is important to handle errors accordingly and part of it is to perform retry only when is needed. So if we take a look at the Slack documentation for errors and rate limits we can take the following actions regarding the status obtained on each request:
- Status 429: Retry
- Status 4XX: Don't retry
- Status 500: Retry

Slack documentation:
- https://api.slack.com/messaging/webhooks#handling_errors
- https://api.slack.com/changelog/2016-05-17-changes-to-errors-for-incoming-webhooks
- https://api.slack.com/docs/rate-limits#rate-limits__responding-to-rate-limiting-conditions


To implement this we need to identify errors that need retries from those that don't require it, for this, we will use tenacity's *retry_if_exception_type* function along with a custom Exception *SendMsgError*. On top of that, we need to do some improvement to the *send_msg_slack* function to cover our requirements.

Below we can see the changes in the function along with the retry decorator. The complete code can be seen on the [slack_retries_v2.py](./slack_retries_v2.py) file.

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
```
Let's check the result of the execution of this new version:
```log
python3 slack_retries_v2.py

Testing Webhook
2021-05-08 21:17:04,377 :: DEBUG :: Starting call to '__main__.send_msg_slack', this is the 1st time calling it.
2021-05-08 21:17:04,484 :: DEBUG :: Starting new HTTPS connection (1): hooks.slack.com:443
2021-05-08 21:17:04,978 :: DEBUG :: https://hooks.slack.com:443 "POST /services/XXXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX HTTP/1.1" 200 22
ok

Force failure using a non-existing channel
2021-05-08 21:17:04,982 :: DEBUG :: Starting call to '__main__.send_msg_slack', this is the 1st time calling it.
2021-05-08 21:17:04,985 :: DEBUG :: Starting new HTTPS connection (1): hooks.slack.com:443
2021-05-08 21:17:05,600 :: DEBUG :: https://hooks.slack.com:443 "POST /services/XXXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX HTTP/1.1" 404 None
404 Client Error: Not Found for url: https://hooks.slack.com/services/XXXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

Force failure erro 5XX mock
2021-05-08 21:17:05,602 :: DEBUG :: Starting call to '__main__.send_msg_slack', this is the 1st time calling it.
2021-05-08 21:17:05,605 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 21:17:06,069 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
2021-05-08 21:17:07,075 :: DEBUG :: Starting call to '__main__.send_msg_slack', this is the 2nd time calling it.
2021-05-08 21:17:07,078 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 21:17:07,447 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
2021-05-08 21:17:09,450 :: DEBUG :: Starting call to '__main__.send_msg_slack', this is the 3rd time calling it.
2021-05-08 21:17:09,453 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 21:17:09,920 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
2021-05-08 21:17:13,926 :: DEBUG :: Starting call to '__main__.send_msg_slack', this is the 4th time calling it.
2021-05-08 21:17:13,929 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 21:17:14,310 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
RetryError[<Future at 0x103bf5bb0 state=finished raised SendMsgError>]

Force failure erro 429 mock
2021-05-08 21:17:14,311 :: DEBUG :: Starting call to '__main__.send_msg_slack', this is the 1st time calling it.
2021-05-08 21:17:14,314 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 21:17:14,684 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err429 HTTP/1.1" 429 17
2021-05-08 21:17:15,690 :: DEBUG :: Starting call to '__main__.send_msg_slack', this is the 2nd time calling it.
2021-05-08 21:17:15,692 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 21:17:16,057 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err429 HTTP/1.1" 429 17
2021-05-08 21:17:18,060 :: DEBUG :: Starting call to '__main__.send_msg_slack', this is the 3rd time calling it.
2021-05-08 21:17:18,063 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 21:17:18,442 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err429 HTTP/1.1" 429 17
2021-05-08 21:17:22,447 :: DEBUG :: Starting call to '__main__.send_msg_slack', this is the 4th time calling it.
2021-05-08 21:17:22,450 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 21:17:22,824 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err429 HTTP/1.1" 429 17
RetryError[<Future at 0x103d29640 state=finished raised SendMsgError>]
```

In comparison to the previous results, we now see that we have different behavior for errors 404 and 500. In the case of the 404 error, we have only one call as in this case no retry is required. 

We also included a test with a 429 status mock. Similar to the 500 mock we can see the retries. Even if we are doing retries for this type of error, our solution is not complete. According to Slack [documentation](https://api.slack.com/docs/rate-limits#rate-limits__responding-to-rate-limiting-conditions), 429 error response includes a header that indicates the period of backoff that we need to honor and we are not taking that info into account in our retry policy.

### Include external input into retries

Slack 429 response includes the Retry-After header with the number of seconds that we need to wait to run the next request. With this in mind, the new retry policy shall:
- Maintain the default policy backoff times for cases in which the response does not prescribe a backoff time.
- Implement a mechanism to read and use the backoff time provided by the API.
- Keep the same number of retries as before.

The proposed solution uses tenacity capacity for [custom callbacks](https://tenacity.readthedocs.io/en/latest/#other-custom-callbacks). For our needs we generate a function that returns the wait time as specified by the Slack Response, this function will be used on the [wait hook](https://tenacity.readthedocs.io/en/latest/#waiting-before-retrying) provided by tenacity. 

We still need to solve how to pass the wait time from the *send_msg_slack* to tenacity. In tenacity, any custom callback receives as a parameter the [RetryState](https://tenacity.readthedocs.io/en/latest/#retrycallstate). With the RetryState we could access the function being wrapped by the retry call and the parameters of the function. With this, we tried to use [function attributes](https://www.python.org/dev/peps/pep-0232/), but unfortunately, this approach didn't work, so we resorted to using classes to pass information between tenacity and the retry function.

The new version of the code can be found at [slack_retries_v3.py](./slack_retries_v3.py)
```python
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
    return wait_exponential(multiplier=1, min=4, max=10)(retry_state)
    
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
````

Now we will see the results of these changes:
```log
python3 slack_retries_v3.py

Testing Webhook
2021-05-08 23:15:27,417 :: DEBUG :: Starting call to '__main__.SlackPub.send_msg_slack', this is the 1st time calling it.
2021-05-08 23:15:27,530 :: DEBUG :: Starting new HTTPS connection (1): hooks.slack.com:443
2021-05-08 23:15:28,070 :: DEBUG :: https://hooks.slack.com:443 "POST /services/XXXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX HTTP/1.1" 200 22
ok

Force failure using a non-existing channel
2021-05-08 23:15:28,073 :: DEBUG :: Starting call to '__main__.SlackPub.send_msg_slack', this is the 1st time calling it.
2021-05-08 23:15:28,078 :: DEBUG :: Starting new HTTPS connection (1): hooks.slack.com:443
2021-05-08 23:15:28,656 :: DEBUG :: https://hooks.slack.com:443 "POST /services/XXXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX HTTP/1.1" 404 None
404 Client Error: Not Found for url: https://hooks.slack.com/services/XXXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

Force failure erro 5XX mock
2021-05-08 23:15:28,659 :: DEBUG :: Starting call to '__main__.SlackPub.send_msg_slack', this is the 1st time calling it.
2021-05-08 23:15:29,276 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 23:15:29,920 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
2021-05-08 23:15:30,925 :: DEBUG :: Starting call to '__main__.SlackPub.send_msg_slack', this is the 2nd time calling it.
2021-05-08 23:15:30,928 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 23:15:31,303 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
2021-05-08 23:15:33,308 :: DEBUG :: Starting call to '__main__.SlackPub.send_msg_slack', this is the 3rd time calling it.
2021-05-08 23:15:33,320 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 23:15:33,698 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
2021-05-08 23:15:37,701 :: DEBUG :: Starting call to '__main__.SlackPub.send_msg_slack', this is the 4th time calling it.
2021-05-08 23:15:37,705 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 23:15:38,080 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err500 HTTP/1.1" 500 12
RetryError[<Future at 0x10b188e20 state=finished raised SendMsgError>]

Force failure erro 429 mock
2021-05-08 23:15:38,081 :: DEBUG :: Starting call to '__main__.SlackPub.send_msg_slack', this is the 1st time calling it.
2021-05-08 23:15:38,084 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 23:15:38,451 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err429 HTTP/1.1" 429 17
2021-05-08 23:15:41,453 :: DEBUG :: Starting call to '__main__.SlackPub.send_msg_slack', this is the 2nd time calling it.
2021-05-08 23:15:41,456 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 23:15:41,829 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err429 HTTP/1.1" 429 17
2021-05-08 23:15:44,835 :: DEBUG :: Starting call to '__main__.SlackPub.send_msg_slack', this is the 3rd time calling it.
2021-05-08 23:15:44,837 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 23:15:45,221 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err429 HTTP/1.1" 429 17
2021-05-08 23:15:48,222 :: DEBUG :: Starting call to '__main__.SlackPub.send_msg_slack', this is the 4th time calling it.
2021-05-08 23:15:48,225 :: DEBUG :: Starting new HTTP connection (1): XXXXX.mocklab.io:80
2021-05-08 23:15:48,598 :: DEBUG :: http://XXXXX.mocklab.io:80 "POST /err429 HTTP/1.1" 429 17
RetryError[<Future at 0x10b2aeeb0 state=finished raised SendMsgError>]
```

The first two tests worked as expected and add no new info to this case. The important part is the difference in the times from the 500 error retries compared to the times in the 429 error calls.

The following tables show a comparison of those times for each retry:
| Attempt        | Err 500   | Err 429  |
|:-------------:| :-----:   | :---:     |
| 2             | 1         | 3         |
| 3             | 2         | 3         |
| 4             | 4         | 3         |

As we see in the results, now the times for 429 errors are fixed in 3 secs, which is the value returned by the 429 mock URL and thus the result we expected.

# Conclusion

Tenacity is a very versatile library that can easily help you implement retry policies in a non-invasive manner in your code.
The code shown is an option to solve a common use case, but surely there would be other alternatives that better suit your needs, but we think this code snipes would help in using some useful tenacity features.

Other interesting use cases on which tenacity could help is the calls to Services using libraries such as calls to AWS using boto.


