import datetime
from peewee import Model, CharField, DateTimeField, SqliteDatabase, TextField


db = SqliteDatabase("articles.db")


class db_ArticleHash(Model):
    url = CharField(unique=True)
    hash = CharField()
    date = DateTimeField(default=datetime.datetime.now)
    title = CharField()
    content = TextField()
    img = CharField()
    main_category = CharField()
    subcategory = CharField()

    class Meta:
        database = db


# データベースとテーブルの作成
db.connect()
db.create_tables([db_ArticleHash])


