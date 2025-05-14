from datetime import date
from peewee import *
from config import conf


db_conf = conf["db"]

db = MySQLDatabase(
    database=db_conf["database"],
    host=db_conf["host"],
    user=db_conf["user"],
    password=db_conf["password"],
)


class Margin(Model):
    token = CharField()
    amount = FloatField()
    value = FloatField()
    collateral_ratio = FloatField()
    collateral_value = FloatField()

    class Meta:
        database = db


class Position(Model):
    symbol = CharField()
    direction = CharField()
    amount = FloatField()
    value = FloatField()
    entry_price = FloatField()
    price = FloatField()
    liq_price = FloatField()
    funding_rate = FloatField()
    upl = FloatField()

    class Meta:
        database = db


class Spot(Model):
    token = CharField()
    amount = FloatField()
    price = FloatField()
    value = FloatField()

    class Meta:
        database = db


class Order(Model):
    symbol = CharField()
    direction = CharField()
    amount = FloatField()
    price = FloatField()
    value = FloatField()

    class Meta:
        database = db


db.create_tables([Position, Margin, Spot, Order])
