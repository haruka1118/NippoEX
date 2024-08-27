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
    news_dict = {}

    # 複数のURLに対応するためのリスト
    urls = [
        # "https://www.iwate-np.co.jp/article/category/main",  # 県内_主要
        "https://www.iwate-np.co.jp/article/kyodo/category/national",  # 県内_経済
        "https://www.iwate-np.co.jp/article/category/medical",  # 県内_医療・福祉
        "https://www.iwate-np.co.jp/article/category/politics",  # 県内_行政
        "https://www.iwate-np.co.jp/article/category/education",  # 県内_教育
        "https://www.iwate-np.co.jp/article/category/election",  # 県内_選挙
        "https://www.iwate-np.co.jp/article/category/entertainment",  # 県内_エンタメ
        # "https://www.iwate-np.co.jp/obituary",  # 県内_訃報
        # "https://www.iwate-np.co.jp/page/iwate-bear",  # 県内_クマ情報
        # "https://www.iwate-np.co.jp/page/tohokudo"  # 県内_東北自動車道交通情報
        # "https://www.iwate-np.co.jp/article/kyodo/category/main",  # 全国_主要
        "https://www.iwate-np.co.jp/article/kyodo/category/national",  # 全国_社会
        "https://www.iwate-np.co.jp/article/kyodo/category/politics",  # 全国_政治
        "https://www.iwate-np.co.jp/article/kyodo/category/economics",  # 全国_経済
        "https://www.iwate-np.co.jp/article/kyodo/category/world",  # 全国_国際
        "https://www.iwate-np.co.jp/article/kyodo/category/sports",  # 全国_スポーツ
        "https://www.iwate-np.co.jp/article/oricon",  # 全国_エンタメ
        "https://www.iwate-np.co.jp/article/kyodo/category/lifestyle",  # 全国_暮らし・話題
        "https://www.iwate-np.co.jp/article/kyodo/category/cluture",  # 全国_文化・芸能
        "https://www.iwate-np.co.jp/article/kyodo/category/science",  # 全国_科学・環境・医療・健康
        "https://www.iwate-np.co.jp/article/category/sports",  # スポーツ_岩手のスポーツ
        "https://www.iwate-np.co.jp/article/category/major",  # スポーツ_輝け県人メジャーリーガー
        "https://www.iwate-np.co.jp/article/category/hsbaseball",  # スポーツ_高校野球
        "https://www.iwate-np.co.jp/article/category/npb",  # スポーツ_プロ野球
        "https://www.iwate-np.co.jp/article/category/grulla",  # スポーツ_いわてグルージャ盛岡
        "https://www.iwate-np.co.jp/article/category/seawaves",  # スポーツ_釜石シーウェイブス
        "https://www.iwate-np.co.jp/article/category/bigbulls",  # スポーツ_岩手ビッグブルズ
        "https://www.iwate-np.co.jp/article/category/sumo",  # スポーツ_郷土力士
        # "https://www.iwate-np.co.jp/article/category/shinsai",  # 防災_東日本大震災
        # "https://www.iwate-np.co.jp/weather",  # 防災_防災情報
        # "https://www.iwate-np.co.jp/article/category/disaster",  # 防災_防災・災害
        # "https://www.iwate-np.co.jp/article/category/tendenko",  # 防災_津波てんでんこ
        # "https://www.iwate-np.co.jp/page/kodokiroku",  # 防災_犠牲者の行動記録
        # "https://www.iwate-np.co.jp/article/category/ashiato",  # 防災_震災企画「あしあと」
        # "https://www.iwate-np.co.jp/article/category/ilc",  # 企画特集_ＩＬＣ東北誘致
        # "https://www.iwate-np.co.jp/article/category/nie",  # 企画特集_ＮＩＥいわて
        # "https://www.iwate-np.co.jp/article/category/NIB",  # 企画特集_ＮＩＢ講座「新トレ」
        # "https://www.iwate-np.co.jp/article/category/sakura",  # 企画特集_さくらだより
        # "https://www.iwate-np.co.jp/article/category/oto",  # 企画特集_いわて音巡り
        # "https://www.iwate-np.co.jp/article/category/takuboku-kenji",  # 企画特集_啄木・賢治
        # "https://www.iwate-np.co.jp/article/category/bookseller",  # 企画特集_ベストセラーズ
        # "https://www.iwate-np.co.jp/article/category/tokumei",  # 企画特集_特命記者－あなたの疑問、徹底解明－
        # "https://www.iwate-np.co.jp/page/tsunagu",  # 企画特集_つなぐ　農・食・命
        # "https://www.iwate-np.co.jp/content/madaminukeshikihe/",  # 企画特集_まだ見ぬ景色へ
        # "https://www.iwate-np.co.jp/article/category/high_school_photo",  # 企画特集_高校生フォトコンテスト
        # "https://www.iwate-np.co.jp/article/category/branch-diary",  # 連載・コラム_支局日誌
        # "https://www.iwate-np.co.jp/article/category/working_mother",  # 連載・コラム_ワーママ＆パパ修業中
        # "https://www.iwate-np.co.jp/article/category/suzusan",  # 連載・コラム_＃あちこちのすずさん
        # "https://www.iwate-np.co.jp/article/category/iwate",  # おでかけ_おでかけニュース
        # "https://www.iwate-np.co.jp/experience/event",  # おでかけ_イベント案内
        # "https://www.iwate-np.co.jp/article/category/trekking",  # おでかけ_Today's I Nature
        # "https://www.iwate-np.co.jp/article/category/world-heritage",  # おでかけ_世界遺産
        # "https://www.iwate-np.co.jp/page/kafun"  # おでかけ_スギ・ヒノキ花粉予報
    ]

    seen_articles = set()  # 記事のURLを保存して、重複をチェックするためのセット

    for url in urls:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")

        # 各ページのカテゴリを取得
        categories = [h2 for h2 in soup.find_all("h2") if "align-center h2-title" not in h2.get("class", [])]

        for category in categories:
            category_name = category.text.strip()
            if category_name not in news_dict:
                news_dict[category_name] = []

            # `ul` タグ内の `li` タグを取得する
            # `class="current"` を持つ `li` タグを選択
            ul = category.find_next("ul")
            if ul:
                articles = ul.find_all("li", class_="current")

                for article in articles:
                    headline = article.find("div", class_="headline").text.strip()
                    image_url = article.find("img", class_="lazyload")["data-src"]
                    article_url = article.find("a")["href"]

                    # 重複チェック: 記事のURLが既に見られたものであればスキップ
                    if article_url in seen_articles:
                        continue
                    # 記事URLをセットに追加
                    seen_articles.add(article_url)

                    # 詳細ページにアクセスして本文全体を取得
                    article_response = requests.get(article_url)
                    article_soup = BeautifulSoup(article_response.text, "html.parser")
                    content_parts = article_soup.find("span", class_="article-text body-text").find_all("p")
                    content = "\n".join([p.text.strip() for p in content_parts])

                    news_dict[category_name].append(
                        {
                            "headline": headline,
                            "image_url": image_url,
                            "content": content,
                            "url": article_url,
                            "category": category_name,  # カテゴリ情報を追加
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

    message = f"\n【{article['category']}】\n{article['headline']}\n\n{article['content']}\n\n記事全文>> {article['url']}"

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
    for category, articles in news.items():
        for article in articles:
            send_news_via_line(article)
    return "News sent via LINE!"


if __name__ == "__main__":
    # 定期的に記事をチェックするスレッドを開始
    threading.Thread(target=check_for_updates, daemon=True).start()
    app.run(debug=True)
