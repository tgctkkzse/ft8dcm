#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class ft8slack:
    def __init__(self,slack_api_token):
        self.slack_api_token = slack_api_token
        
    def send_slack_message(self,text,channel):
        self.client = WebClient(token=self.slack_api_token)

        try:
            self.response = self.client.chat_postMessage(
                channel=channel,
                text=text
            )
        except SlackApiError as e:
             print(e)

if __name__ == "__main__":
    ft8slack = ft8slack('sloack token')
    ft8slack.send_slack_message('test',"C07NBH1SAQ5")
