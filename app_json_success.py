import os
import json
import hashlib
import requests
from flask import Flask, render_template
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# ニュース記事のURLリスト
urls = {
    "県内ニュース": [
        ("主要", "https://www.iwate-np.co.jp/article/category/main"),
        ("経済", "https://www.iwate-np.co.jp/article/category/economy"),
        ("医療・福祉", "https://www.iwate-np.co.jp/article/category/medical"),
        ("行政", "https://www.iwate-np.co.jp/article/category/politics"),
        ("教育", "https://www.iwate-np.co.jp/article/category/education"),
        ("選挙", "https://www.iwate-np.co.jp/article/category/election"),
        ("エンタメ", "https://www.iwate-np.co.jp/article/category/entertainment"),
    ]
}

# LINE Notifyのトークン
LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN")


def send_line_notify(message, image_url=None):
    headers = {
        "Authorization": f"Bearer {LINE_NOTIFY_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload = {"message": message}
    if image_url:
        payload["imageThumbnail"] = image_url
        payload["imageFullsize"] = image_url

    response = requests.post("https://notify-api.line.me/api/notify", headers=headers, data=payload)
    return response


def fetch_article_content(article_url):
    response = requests.get(article_url)
    soup = BeautifulSoup(response.text, "html.parser")

    content_span = soup.find("span", class_="article-text body-text")

    if content_span:
        paragraphs = content_span.find_all("p")
        content = "\n".join([p.text.strip() for p in paragraphs])
        return content
    return "本文を取得できませんでした。"


def fetch_articles(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    articles = soup.select("div.article-list-right-box ul.article-list li.item")

    article_list = []
    for article in articles:
        title = article.find("span", class_="full").text.strip()
        link = article.find("a")["href"]
        full_link = f"{link}"
        img_tag = article.find("img", class_="lazyload")
        img = img_tag["data-src"] if img_tag else None
        date = article.find("span", class_="date").text.strip()

        content = fetch_article_content(full_link)
        hash_value = hashlib.md5(content.encode("utf-8")).hexdigest()

        article_list.append(
            {
                "title": title,
                "link": full_link,
                "image": img,
                "content": content,
                "hash": hash_value,
                "date": date,
            }
        )

    return article_list


HASH_FILE = "article_hashes.json"


def load_hashes():
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_hashes(hashes):
    with open(HASH_FILE, "w", encoding="utf-8") as f:
        json.dump(hashes, f, ensure_ascii=False, indent=4)


def check_for_updates(articles):
    previous_hashes = load_hashes()
    new_hashes = {}
    new_articles = []

    for article in articles:
        url = article["link"]
        current_hash = article["hash"]

        if url not in previous_hashes or previous_hashes[url] != current_hash:
            new_articles.append(article)

        new_hashes[url] = current_hash

    save_hashes(new_hashes)

    return new_articles


def scheduled_task():
    all_articles = {}
    updated_articles = []

    for main_category, subcategories in urls.items():
        all_articles[main_category] = {}
        for subcategory, url in subcategories:
            articles = fetch_articles(url)
            new_articles = check_for_updates(articles)
            all_articles[main_category][subcategory] = articles
            updated_articles.extend(new_articles)

    # 配信済みの記事を保持するためのファイル
    distributed_articles_file = "distributed_articles.json"
    if os.path.exists(distributed_articles_file):
        with open(distributed_articles_file, "r", encoding="utf-8") as f:
            distributed_articles = json.load(f)
    else:
        distributed_articles = {}

    # 新しい記事だけを配信
    for article in updated_articles:
        url = article["link"]
        if url not in distributed_articles:
            title = article["title"]
            link = article["link"]
            image = article["image"]
            content = article["content"]
            date = article["date"]

            message = f"{date}\n【{title}】\n\n{content}\n\n記事全文>>{link}"
            send_line_notify(message, image)

            # 配信済み記事リストに追加
            distributed_articles[url] = article
            with open(distributed_articles_file, "w", encoding="utf-8") as f:
                json.dump(distributed_articles, f, ensure_ascii=False, indent=4)


# スケジューラの設定
scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_task, "interval", minutes=2)
scheduler.start()


@app.route("/")
def index():
    all_articles = {}

    for main_category, subcategories in urls.items():
        all_articles[main_category] = {}
        for subcategory, url in subcategories:
            articles = fetch_articles(url)
            all_articles[main_category][subcategory] = articles

    return render_template("index.html", all_articles=all_articles)


if __name__ == "__main__":
    app.run(debug=True)
