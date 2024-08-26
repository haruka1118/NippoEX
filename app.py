from flask import Flask, render_template
import requests
from bs4 import BeautifulSoup
import threading
import time

app = Flask(__name__)

LINE_NOTIFY_TOKEN = "N3rzw8u4xQXfQgZ3oTKVz14N8721m2hTmJ8dhgV0Ws7"
LINE_NOTIFY_API = "https://notify-api.line.me/api/notify"

# 変数をグローバルに保持して、前回の記事内容を保存します
previous_news_dict = {}


def fetch_latest_news():
    url = "https://www.iwate-np.co.jp/article/category/main"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    news_dict = {}

    categories = soup.find_all("h2")

    for category in categories:
        category_name = category.text.strip()
        news_dict[category_name] = []

        articles = category.find_next("ul").find_all("li", class_="item current")

        for article in articles:
            headline = article.find("div", class_="headline").text.strip()
            image_url = article.find("img", class_="lazyload")["data-src"]
            article_url = article.find("a")["href"]

            # 詳細ページにアクセスして本文全体を取得
            article_response = requests.get(article_url)
            article_soup = BeautifulSoup(article_response.text, "html.parser")
            # 本文全体を取得（複数の p タグがある場合）
            content_parts = article_soup.find("span", class_="article-text body-text").find_all("p")
            content = "\n".join([p.text.strip() for p in content_parts])

            news_dict[category_name].append(
                {
                    "headline": headline,
                    "image_url": image_url,
                    "content": content,
                    "url": article_url,
                }
            )

    return news_dict


def check_for_updates():
    global previous_news_dict

    while True:
        current_news_dict = fetch_latest_news()

        # 前回の内容と比較して変更があるかチェック
        for category, articles in current_news_dict.items():
            if category not in previous_news_dict:
                previous_news_dict[category] = articles
                continue

            for i, article in enumerate(articles):
                if (
                    i >= len(previous_news_dict[category])
                    or article["headline"] != previous_news_dict[category][i]["headline"]
                ):
                    send_news_via_line(article)
                    print(f"New article found: {article['headline']}")

        previous_news_dict = current_news_dict

        # 10分ごとにチェック
        time.sleep(60)


def send_news_via_line(article):
    headers = {"Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"}

    message = f"\n【{article['headline']}】\n\n{article['content']}\n\n記事全文>> {article['url']}"

    # `imageFullsize` にも同じ画像URLを指定
    data = {
        "message": message,
        "imageThumbnail": article['image_url'],  # サムネイル画像のURL
        "imageFullsize": article['image_url']    # フルサイズ画像のURL（同じURLを指定）
    }

    response = requests.post(LINE_NOTIFY_API, headers=headers, data=data)
    if response.status_code == 200:
        print(f"Message sent: {message}")
    else:
        print(f"Failed to send message: {response.status_code}, Response: {response.text}")


@app.route("/")
def index():
    news = fetch_latest_news()
    return render_template("index.html", news=news)


@app.route("/send-news")
def send_news():
    news = fetch_latest_news()
    for category, articles in news.items():
        for article in articles:
            send_news_via_line(article)
    return "News sent via LINE!"


if __name__ == "__main__":
    # 定期的に記事をチェックするスレッドを開始
    threading.Thread(target=check_for_updates, daemon=True).start()
    app.run(debug=True)
