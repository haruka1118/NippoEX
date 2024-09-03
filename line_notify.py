import os
from dotenv import load_dotenv
import requests


# LINE Notifyのトークン
load_dotenv()
LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN")


def send_line_notify(message):
    headers = {
        "Authorization": f"Bearer {LINE_NOTIFY_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    line_message = {"message": message}

    response = requests.post("https://notify-api.line.me/api/notify", headers=headers, data=line_message)
    return response
