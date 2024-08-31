import os
from dotenv import load_dotenv
import requests


# LINE Notifyのトークン
load_dotenv()
LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN")


def send_line_notify(message, image_url=None):
    headers = {
        "Authorization": f"Bearer {LINE_NOTIFY_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    line_message = {"message": message}
    # if image_url:
    #     line_message["imageThumbnail"] = image_url
    #     line_message["imageFullsize"] = image_url

    response = requests.post("https://notify-api.line.me/api/notify", headers=headers, data=line_message)
    return response
