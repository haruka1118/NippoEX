import datetime
import os
import hashlib
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
from db import db_ArticleHash
from flask import Flask, render_template, send_file
from line_notify import send_line_notify
from urls import urls


app = Flask(__name__)


# 1)記事ページ(article_url)から記事本文を取得
def fetch_article_content(article_url):
    response = requests.get(article_url)
    soup = BeautifulSoup(response.text, "html.parser")

    content_span = soup.find("span", class_="article-text body-text")
    if content_span:
        paragraphs = content_span.find_all("p")
        content = "\n".join([p.text.strip() for p in paragraphs])
        return content
    return "本文を取得できませんでした。"


# 2)中カテゴリページ(url)から情報を取得
def fetch_articles(url, main_category, subcategory):
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
        date_nippo = date_tag.text.strip() if date_tag else "日付不明"

        # 記事内容の取得
        content = fetch_article_content(full_link)

        # コンテンツをハッシュ化
        hash_value = hashlib.md5(content.encode("utf-8")).hexdigest()

        article_list.append(
            {
                "title": title,
                "link": full_link,
                "image": img,
                "content": content,
                "hash": hash_value,
                "date_nippo": date_nippo,
                "main_category": main_category,
                "subcategory": subcategory,
            }
        )

    return article_list


def check_for_updates(articles):
    new_articles = []

    for article in articles:
        url = article["link"]
        current_hash = article["hash"]

        # データベース内のURL(ユニーク)を比較
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
                date_now=datetime.datetime.now(),
                date_nippo=article["date_nippo"],
                main_category=article["main_category"],
                subcategory=article["subcategory"],
            ).on_conflict(
                conflict_target=[db_ArticleHash.url],
                update={
                    db_ArticleHash.hash: current_hash,
                    db_ArticleHash.title: article["title"],
                    db_ArticleHash.content: article["content"],
                    db_ArticleHash.img: article["image"],
                    db_ArticleHash.date_now: datetime.datetime.now(),
                    db_ArticleHash.date_nippo: article["date_nippo"],
                    db_ArticleHash.main_category: article["main_category"],
                    db_ArticleHash.subcategory: article["subcategory"],
                },
            ).execute()

    return new_articles


def scheduled_task():
    updated_articles = []

    for main_category, subcategories in urls.items():  # urls.pyから「main_category」定義
        for subcategory, url in subcategories:  # urls.pyから「subcategory, url」定義
            articles = fetch_articles(url, main_category, subcategory)  # 「articles」定義
            new_articles = check_for_updates(articles)
            updated_articles.extend(new_articles)  # フラットなリストになるように追加はextend()

    for article in updated_articles:
        title = article["title"]
        link = article["link"]
        image = article["image"]
        content = article["content"]
        date_nippo = article["date_nippo"]

        message = f"{date_nippo}【{article['main_category']}】({article['subcategory']})\n◆{title}\n\n{content}\n\n記事全文>>{link}"

        send_line_notify(message, image)


# スケジューラの設定
scheduler = BackgroundScheduler()  # スケジューラーのインスタンスを作成
scheduler.add_job(scheduled_task, "interval", minutes=3)  # スケジュールを設定
scheduler.start()  # スケジューラーの開始


@app.route("/")  # URLと以下のPython関数を結びつける
def index():
    all_articles = {}

    for main_category, subcategories in urls.items():
        all_articles[main_category] = {}
        for subcategory, url in subcategories:
            # データベースから記事を取得
            articles = (
                db_ArticleHash.select()
                .where(db_ArticleHash.main_category == main_category)
                .where(db_ArticleHash.subcategory == subcategory)
                .order_by(db_ArticleHash.date_now.desc())
            )

            # データをリストに変換
            article_list = [
                {
                    "title": article.title,
                    "link": article.url,
                    "image": article.img,
                    "content": article.content,
                    "date_now": article.date_now.strftime("%Y-%m-%d %H:%M"),
                    "date_nippo": article.date_nippo,
                }
                for article in articles
            ]
            all_articles[main_category][subcategory] = article_list

    return render_template("index.html", all_articles=all_articles)


@app.route("/download-db")
def download_db():
    return send_file("articles.db", as_attachment=True)


if __name__ == "__main__":  # このスクリプトが直接実行されたときにだけ、この条件が True になるという意味
    port = int(os.getenv("PORT", 5000))  # dotenvにportがあればそれ、なければ5000
    app.run(host="0.0.0.0", port=port)  # どこからでもこのプログラムにアクセスできるように
