import pymysql
from flask import g

from app.config import DB_CONFIG


def get_db():
    if 'db' not in g:
        g.db = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **DB_CONFIG)
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def query(sql, params=(), one=False):
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def execute(sql, params=()):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(sql, params)
        last_id = cur.lastrowid
    db.commit()
    return last_id
