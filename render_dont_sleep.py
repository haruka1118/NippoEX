import requests
from apscheduler.schedulers.background import BackgroundScheduler


def dont_sleep():
    URL = "https://nippoex.onrender.com"

    try:
        # URLにリクエストを送る
        response = requests.get(URL)
        print(f"Response Status Code: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")


# スケジューラの設定
scheduler = BackgroundScheduler()
scheduler.add_job(dont_sleep, "interval", minutes=10)  # 10分ごとに実行
scheduler.start()

# メインの処理をループで待機（またはFlaskアプリの場合、app.run()などを実行）
try:
    while True:
        pass  # 無限ループでプロセスを維持（通常のWebアプリであればapp.run()などに置き換え）
except (KeyboardInterrupt, SystemExit):
    scheduler.shutdown()  # プログラム終了時にスケジューラを停止
