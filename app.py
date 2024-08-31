import os
from dotenv import load_dotenv
import hashlib
import requests
from flask import Flask, render_template
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler
from peewee import Model, CharField, DateTimeField, SqliteDatabase, TextField
import datetime
from urls import urls

# SQLiteデータベースの設定
db = SqliteDatabase("articles.db")


class db_ArticleHash(Model):
    url = CharField(unique=True)
    hash = CharField()
    date = DateTimeField(default=datetime.datetime.now)
    title = CharField()
    content = TextField()
    img = CharField()

    class Meta:
        database = db


# データベースとテーブルの作成
db.connect()
db.create_tables([db_ArticleHash])

app = Flask(__name__)


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


# 記事本文を取得
def fetch_article_content(article_url):
    response = requests.get(article_url)
    soup = BeautifulSoup(response.text, "html.parser")

    content_span = soup.find("span", class_="article-text body-text")
    if content_span:
        paragraphs = content_span.find_all("p")
        content = "\n".join([p.text.strip() for p in paragraphs])
        return content
    return "本文を取得できませんでした。"


# 中カテゴリページから情報を取得
def fetch_articles(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    if "kyodo" in url:
        # 全国ニュース(広告除外)
        ads = soup.select("aside.side, .news-box")
        for ad in ads:
            ad.decompose()
        articles = soup.select("ul.article-list li")
    else:
        # 県内ニュース(広告除外)
        ads = soup.select("aside.side, .news-box")
        for ad in ads:
            ad.decompose()
        articles = soup.select("div.article-list-right-box ul.article-list li.item")

    article_list = []
    for article in articles:
        # タイトルの取得
        title_tag = article.find("div", class_="headline")
        title = "タイトル不明"
        if title_tag:
            title_span = title_tag.find("span", class_="full")
            title = title_span.text.strip() if title_span else title_tag.text.strip()

        # リンクの取得
        link_tag = article.find("a", class_="article-list-anchor")
        link = link_tag.get("href", "#")
        full_link = link if link.startswith("http") else f"https://www.iwate-np.co.jp{link}"

        # 画像の取得
        img_tag = article.find("img", class_="lazyload")
        img = img_tag.get("data-src")

        # 日付の取得
        date_tag = article.find("span", class_="date")
        date = date_tag.text.strip() if date_tag else "日付不明"

        # 記事内容の取得
        content = fetch_article_content(full_link)

        # URLの最後から4番目、3番目、2番目、1番目の部分を取得し、ハッシュ化
        combined_parts, hash_value = get_and_hash_combined_parts(full_link)

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


def get_and_hash_combined_parts(url):
    # URLを"/"で分割してリストにする
    url_parts = url.rstrip("/").split("/")

    # ハッシュ化する部分を格納するリスト
    parts_to_hash = []

    # # URLが十分に長いか確認
    # if len(url_parts) >= 4:
    # 最後から4番目、3番目、2番目、1番目の部分を取り出す
    for i in range(4, 0, -1):
        if len(url_parts) >= i:
            parts_to_hash.append(url_parts[-i])

    # 取得した部分をひとつにまとめる
    combined_parts = "/".join(parts_to_hash)

    # ひとつにまとめた部分をハッシュ化する
    hash_value = hashlib.md5(combined_parts.encode("utf-8")).hexdigest()

    return combined_parts, hash_value


def check_for_updates(articles):
    new_articles = []

    for article in articles:
        url = article["link"]
        current_hash = article["hash"]

        # データベース内でハッシュ値を確認
        db_article = db_ArticleHash.get_or_none(db_ArticleHash.url == url)

        if db_article is None or db_article.hash != current_hash:
            new_articles.append(article)

            # 新しいハッシュ値をデータベースに保存
            db_ArticleHash.insert(
                url=url,
                hash=current_hash,
                title=article["title"],
                content=article["content"],
                img=article["image"],
                date=datetime.datetime.now(),
            ).on_conflict(
                conflict_target=[db_ArticleHash.url], update={db_ArticleHash.hash: current_hash}
            ).execute()

    return new_articles


def scheduled_task():
    updated_articles = []

    for main_category, subcategories in urls.items():
        for subcategory, url in subcategories:
            articles = fetch_articles(url)
            new_articles = check_for_updates(articles)
            updated_articles.extend(new_articles)

    for article in updated_articles:
        title = article["title"]
        link = article["link"]
        image = article["image"]
        content = article["content"]
        date = article["date"]

        message = f"{date}【{main_category}】({subcategory})\n◆{title}\n\n{content}\n\n記事全文>>{link}"

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
    port = int(os.getenv("PORT", 5000))  # dotenvにportがあればそれ、なければ5000
    app.run(host="0.0.0.0", port=port)  # どこからでもこのプログラムにアクセスできるように

# 定期スケジュールで記事の情報もDBにいれる
# DBからLPにだす
# LPは降順(記事の取得日時)
