import requests
import time


# アクセスしたいURLを指定します
def dont_sleep():
    URL = "https://nippoex.onrender.com"

    # リクエストを送る間隔（秒）
    INTERVAL = 60 * 10  # 10分

    # 最大リトライ回数
    MAX_RETRIES = 5

    retries = 0

    while retries < MAX_RETRIES:
        try:
            # URLにリクエストを送る
            response = requests.get(URL)
            print(f"Response Status Code: {response.status_code}")
            retries = 0  # 成功したらリトライカウントをリセット
        except Exception as e:
            print(f"Error: {e}")
            retries += 1  # エラーが発生したらリトライカウントを増やす

        # 指定した間隔だけ待つ
        time.sleep(INTERVAL)

    # 最大リトライ回数を超えた場合のメッセージ
    print("Max retries exceeded, stopping the script.")


dont_sleep()
