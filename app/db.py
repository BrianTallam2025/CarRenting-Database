import pymysql
from contextlib import contextmanager

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
    try:
        with db.cursor() as cur:
            cur.execute(sql, params)
            last_id = cur.lastrowid
        db.commit()
        return last_id
    except Exception:
        db.rollback()
        raise


@contextmanager
def transaction():
    """Run several statements on one connection and commit them together."""
    db = get_db()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
