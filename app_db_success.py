import os
import hashlib
import requests
from flask import Flask, render_template
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler
from peewee import Model, CharField, DateTimeField, SqliteDatabase
import datetime

# SQLiteデータベースの設定
db = SqliteDatabase("articles.db")


class BaseModel(Model):
    class Meta:
        database = db


class ArticleHash(BaseModel):
    url = CharField(unique=True)
    hash = CharField()
    date = DateTimeField(default=datetime.datetime.now)


# データベースとテーブルの作成
db.connect()
db.create_tables([ArticleHash])

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
    ],
    "全国ニュース": [
        ("主要", "https://www.iwate-np.co.jp/article/kyodo/category/main"),
        ("社会", "https://www.iwate-np.co.jp/article/kyodo/category/national"),
        ("政治", "https://www.iwate-np.co.jp/article/kyodo/category/politics"),
        ("経済", "https://www.iwate-np.co.jp/article/kyodo/category/economics"),
        ("国際", "https://www.iwate-np.co.jp/article/kyodo/category/world"),
        ("スポーツ", "https://www.iwate-np.co.jp/kyodo/category/sports"),
        ("エンタメ", "https://www.iwate-np.co.jp/article/oricon"),
        ("暮らし・話題", "https://www.iwate-np.co.jp/article/kyodo/category/lifestyle"),
        ("文化・芸能", "https://www.iwate-np.co.jp/article/kyodo/category/cluture"),
        ("科学・環境・医療・健康", "https://www.iwate-np.co.jp/article/kyodo/category/science"),
    ],
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
        title_tag = article.find("div", class_="headline")
        title = title_tag.text.strip() if title_tag else "タイトル不明"
        link_tag = article.find("a", class_="article-list-anchor")
        link = link_tag["href"] if link_tag else "#"
        full_link = f"{link}"
        img_tag = article.find("img", class_="lazyload")
        img = img_tag["data-src"] if img_tag else None
        date_tag = article.find("span", class_="date")
        date = date_tag.text.strip() if date_tag else "日付不明"

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


def load_hashes():
    hashes = {}
    for article_hash in ArticleHash.select():
        hashes[article_hash.url] = article_hash.hash
    return hashes


def save_hashes(hashes):
    with db.atomic():
        for url, hash_value in hashes.items():
            ArticleHash.insert(url=url, hash=hash_value).on_conflict(
                conflict_target=[ArticleHash.url], update={ArticleHash.hash: hash_value}
            ).execute()


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

    for article in updated_articles:
        title = article["title"]
        link = article["link"]
        image = article["image"]
        content = article["content"]
        date = article["date"]

        message = f"{date}\n【{title}】\n\n{content}\n\n記事全文>>{link}"

        send_line_notify(message, image)


# スケジューラの設定
scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_task, "interval", minutes=5)
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
