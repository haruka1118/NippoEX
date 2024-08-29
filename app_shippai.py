from flask import Flask, render_template
from dotenv import load_dotenv
import os
import requests
from bs4 import BeautifulSoup
import threading
import time
from urls import urls  # ここでURLリストをインポート

load_dotenv()

app = Flask(__name__)

LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN")
LINE_NOTIFY_API = "https://notify-api.line.me/api/notify"

# 前回の記事内容を保存するためのグローバル変数
previous_news_dict = {}


def determine_category(url):
    if "iwate-np.co.jp/article/category/economy" in url or \
       "iwate-np.co.jp/article/category/medical" in url or \
       "iwate-np.co.jp/article/category/politics" in url or \
       "iwate-np.co.jp/article/category/education" in url or \
       "iwate-np.co.jp/article/category/election" in url or \
       "iwate-np.co.jp/article/category/entertainment" in url:
        return "県内ニュース"
    elif "iwate-np.co.jp/article/kyodo/category/national" in url or \
         "iwate-np.co.jp/article/kyodo/category/politics" in url or \
         "iwate-np.co.jp/article/kyodo/category/economics" in url or \
         "iwate-np.co.jp/article/kyodo/category/world" in url or \
         "iwate-np.co.jp/article/kyodo/category/sports" in url or \
         "iwate-np.co.jp/article/oricon" in url or \
         "iwate-np.co.jp/article/kyodo/category/lifestyle" in url or \
         "iwate-np.co.jp/article/kyodo/category/cluture" in url or \
         "iwate-np.co.jp/article/kyodo/category/science" in url:
        return "全国ニュース"
    elif "iwate-np.co.jp/article/category/sports" in url or \
         "iwate-np.co.jp/article/category/major" in url or \
         "iwate-np.co.jp/article/category/hsbaseball" in url or \
         "iwate-np.co.jp/article/category/npb" in url or \
         "iwate-np.co.jp/article/category/grulla" in url or \
         "iwate-np.co.jp/article/category/seawaves" in url or \
         "iwate-np.co.jp/article/category/bigbulls" in url or \
         "iwate-np.co.jp/article/category/sumo" in url:
        return "スポーツ"
    else:
        return "その他"


def fetch_latest_news():
    news_dict = {
        "県内ニュース": {},
        "全国ニュース": {},
        "スポーツ": {},
        "その他": {}
    }

    seen_articles = set()

    for url in urls:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")

        big_category = determine_category(url)

        categories = [h2 for h2 in soup.find_all("h2") if "align-center h2-title" not in h2.get("class", [])]

        for category in categories:
            category_name = category.text.strip()
            if category_name not in news_dict[big_category]:
                news_dict[big_category][category_name] = []

        ul = soup.find("ul", class_="article-list")
        if ul:
            articles = ul.find_all("li", class_="item")

            for article in articles:
                headline = article.find("div", class_="headline").text.strip()
                image_url = article.find("img", class_="lazyload")["data-src"]
                article_url = article.find("a")["href"]

                if article_url in seen_articles:
                    continue
                seen_articles.add(article_url)

                article_response = requests.get(article_url)
                article_soup = BeautifulSoup(article_response.text, "html.parser")
                content_parts = article_soup.find("span", class_="article-text body-text").find_all("p")
                content = "\n".join([p.text.strip() for p in content_parts])

                middle_category = article_soup.find("h2", class_="middle-category").text.strip() if article_soup.find("h2", class_="middle-category") else "その他"

                if middle_category not in news_dict[big_category]:
                    news_dict[big_category][middle_category] = []

                news_dict[big_category][middle_category].append(
                    {
                        "headline": headline,
                        "image_url": image_url,
                        "content": content,
                        "url": article_url,
                        "big_category": big_category,
                        "middle_category": middle_category,
                    }
                )

    # ソート処理（例：記事の追加日時でソート）
    for big_category in news_dict:
        for middle_category in news_dict[big_category]:
            news_dict[big_category][middle_category].sort(key=lambda x: x["headline"])  # 例としてタイトルでソート

    return news_dict


def check_for_updates():
    global previous_news_dict

    while True:
        current_news_dict = fetch_latest_news()

        # 前回の内容と比較して変更があるかチェック
        for big_category, middle_categories in current_news_dict.items():
            if big_category not in previous_news_dict:
                previous_news_dict[big_category] = middle_categories
                continue

            for middle_category, articles in middle_categories.items():
                if middle_category not in previous_news_dict[big_category]:
                    previous_news_dict[big_category][middle_category] = articles
                    continue

                for i, article in enumerate(articles):
                    if i >= len(previous_news_dict[big_category][middle_category]):
                        # 新しい記事
                        send_news_via_line(article)
                        print(f"New article found: {article['headline']}")
                    elif article["headline"] != previous_news_dict[big_category][middle_category][i]["headline"]:
                        # 更新があった場合
                        send_news_via_line(article)
                        print(f"Updated article found: {article['headline']}")

                # 最新の記事を記録する
                previous_news_dict[big_category][middle_category] = articles

        # 10分ごとにチェック
        time.sleep(600)  # 600秒 (10分) に修正


def send_news_via_line(article):
    headers = {"Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"}

    message = f"\n【{article['big_category']} > {article['middle_category']}】\n{article['headline']}\n\n{article['content']}\n\n記事全文>> {article['url']}"

    # `imageFullsize` にも同じ画像URLを指定
    data = {
        "message": message,
        "imageThumbnail": article["image_url"],  # サムネイル画像のURL
        "imageFullsize": article["image_url"],  # フルサイズ画像のURL（同じURLを指定）
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
    for big_category, middle_categories in news.items():
        for middle_category, articles in middle_categories.items():
            for article in articles:
                send_news_via_line(article)
    return "News sent via LINE!"


if __name__ == "__main__":
    # 定期的に記事をチェックするスレッドを開始
    threading.Thread(target=check_for_updates, daemon=True).start()
    app.run(debug=True)
