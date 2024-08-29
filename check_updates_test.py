import hashlib
import json
import os  # ここを追加
from datetime import datetime

def generate_hash(content):
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def save_hashes(hashes):
    try:
        with open('article_hashes.json', 'w', encoding='utf-8') as f:
            json.dump(hashes, f, ensure_ascii=False, indent=4)
        print("Hashes saved successfully.")
    except Exception as e:
        print(f"Error saving hashes: {e}")

def load_hashes():
    if os.path.exists('article_hashes.json'):
        try:
            with open('article_hashes.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading hashes: {e}")
    return {}

def check_for_updates(articles):
    previous_hashes = load_hashes()
    new_hashes = {}
    new_articles = []
    
    for article in articles:
        url = article['link']
        current_hash = generate_hash(article['content'])
        
        if url not in previous_hashes or previous_hashes[url]['hash'] != current_hash:
            new_articles.append(article)
        
        new_hashes[url] = {
            'hash': current_hash,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    save_hashes(new_hashes)
    
    return new_articles

# テスト用の記事データ
test_articles = [
    {
        'link': 'https://example.com/article1',
        'content': '北上市は２５日、江釣子地区にある市立の保育園、幼稚園全３施設の閉園時期を２０２６年３月で検討していることを明らかにした。'
    }
]

# 更新をチェック
new_articles = check_for_updates(test_articles)
print("New Articles:", new_articles)
