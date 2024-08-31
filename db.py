import datetime
from peewee import Model, CharField, DateTimeField, SqliteDatabase, TextField


db = SqliteDatabase("articles.db")


class db_ArticleHash(Model):
    url = CharField(unique=True)
    date_now = DateTimeField(default=datetime.datetime.now)
    date_nippo = DateTimeField()
    main_category = CharField()
    subcategory = CharField()
    title = CharField()
    img = CharField()
    content = TextField()
    hash = CharField()

    class Meta:
        database = db


# データベースとテーブルの作成
db.connect()
db.create_tables([db_ArticleHash])


