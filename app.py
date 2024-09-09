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


def get_and_hash_combined_parts(url):
    # URLを'/'で分割してリストにする
    url_parts = url.rstrip("/").split("/")

    # ハッシュ化する部分を格納するリスト
    parts_to_hash = []

    # URLが十分に長いか確認
    if len(url_parts) >= 4:
        # 最後から4番目、3番目、2番目、1番目の部分を取り出す
        for i in range(4, 0, -1):
            if len(url_parts) >= i:
                parts_to_hash.append(url_parts[-i])

    # 取得した部分をひとつにまとめる
    combined_parts = "/".join(parts_to_hash)

    # ひとつにまとめた部分をハッシュ化する
    hash_value = hashlib.md5(combined_parts.encode("utf-8")).hexdigest()

    return combined_parts, hash_value


# 2)中カテゴリページ(url)から情報を取得
def fetch_articles(url, main_category, subcategory):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    if "kyodo" in url:
        # 全国ニュース(広告除外)
        ads = soup.select("aside.side, .news-box")
        for ad in ads:
            ad.decompose()
        articles = (soup.select("ul.article-list li"))
    else:
        # 県内ニュース(広告除外)
        ads = soup.select("aside.side, .news-box")
        for ad in ads:
            ad.decompose()
        articles = (soup.select("div.article-list-right-box ul.article-list li.item"))

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
        img_tag = article.find("a", class_="article-list-anchor")
        img = img_tag.get("data-picture-src") or img_tag.get("data-src") or img_tag.get("data-srcset")

        # 日付の取得
        date_tag = article.find("span", class_="date")
        date_nippo = date_tag.text.strip() if date_tag else "日付不明"

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
                "date_nippo": date_nippo,
                "main_category": main_category,
                "subcategory": subcategory,
            }
        )

    return article_list


def check_for_updates(articles):
    new_articles = []

    for article in reversed(articles):
        current_hash = article["hash"]

        # データベース内のハッシュ値を比較
        db_article = db_ArticleHash.get_or_none(db_ArticleHash.hash == current_hash)

        if db_article is None:
            new_articles.append(article)

            # 新しいハッシュ値をデータベースに保存
            db_ArticleHash.insert(
                url=article["link"],
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
                    # db_ArticleHash.date_now: datetime.datetime.now(),
                    db_ArticleHash.date_nippo: article["date_nippo"],
                    db_ArticleHash.main_category: article["main_category"],
                    db_ArticleHash.subcategory: article["subcategory"],
                },
            ).execute()

    return new_articles


def scheduled_task():
    updated_articles = []
    link_nippo = "https://nippoex.onrender.com/"

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

        message = f"{date_nippo}【{article['main_category']}】({article['subcategory']})\n◆{title}\n\n{content}\n\n◆記事全文>>{link}\n◆日報EX>>{link_nippo}"

        send_line_notify(message, image)


# スケジューラの設定
scheduler = BackgroundScheduler()  # スケジューラーのインスタンスを作成
scheduler.add_job(scheduled_task, "interval", minutes=1)  # スケジュールを設定
scheduler.start()  # スケジューラーの開始


@app.route("/")
def index():
    all_articles = {}

    for main_category, subcategories in urls.items():
        # データベースから記事を取得
        articles = (
            db_ArticleHash.select()
            .where(db_ArticleHash.main_category == main_category)
            .order_by(db_ArticleHash.date_now.desc())
            .limit(5)
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
        all_articles[main_category] = article_list

    return render_template("index.html", all_articles=all_articles)


@app.route("/kennai_news/")
def kennai_news():
    kennai_news_articles = {}

    for main_category, subcategories in urls.items():
        if main_category == "県内ニュース":
            kennai_news_articles[main_category] = {}
            for subcategory, url in subcategories:
                # データベースから記事を取得
                articles = (
                    db_ArticleHash.select()
                    .where(db_ArticleHash.main_category == main_category)
                    .where(db_ArticleHash.subcategory == subcategory)
                    .order_by(db_ArticleHash.date_now.desc())
                    .limit(5)
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
                kennai_news_articles[main_category][subcategory] = article_list

    return render_template("kennai_news.html", kennai_news_articles=kennai_news_articles)


@app.route("/zenkoku_news/")
def zenkoku_news():
    zenkoku_news_articles = {}

    for main_category, subcategories in urls.items():
        if main_category == "全国ニュース":
            zenkoku_news_articles[main_category] = {}
            for subcategory, url in subcategories:
                # データベースから記事を取得
                articles = (
                    db_ArticleHash.select()
                    .where(db_ArticleHash.main_category == main_category)
                    .where(db_ArticleHash.subcategory == subcategory)
                    .order_by(db_ArticleHash.date_now.desc())
                    .limit(5)
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
                zenkoku_news_articles[main_category][subcategory] = article_list

    return render_template("zenkoku_news.html", zenkoku_news_articles=zenkoku_news_articles)


@app.route("/download-db")
def download_db():
    return send_file("articles.db", as_attachment=True)


if __name__ == "__main__":  # このスクリプトが直接実行されたときにだけ、この条件が True になるという意味
    port = int(os.getenv("PORT", 5000))  # dotenvにportがあればそれ、なければ5000
    app.run(host="0.0.0.0", port=port)  # どこからでもこのプログラムにアクセスできるように
