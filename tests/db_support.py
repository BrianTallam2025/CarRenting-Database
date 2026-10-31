"""Shared MySQL helpers for the database-backed test suites.

Each test module points DB_NAME at its own throwaway database, loads
schema.sql and seed.sql into it, and drops it when the module finishes.
The demo `car_rental` database is never touched.
"""

from pathlib import Path

import pymysql
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
DEMO_PASSWORD = 'demo1234'
PASSWORD_HASH = generate_password_hash(DEMO_PASSWORD)


def _connect(config):
    return pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **config)


def admin_connection(config):
    """Connect without selecting a database, so CREATE/DROP DATABASE works."""
    config = dict(config)
    config.pop('database', None)
    return _connect(config)


def drop_database(config, database):
    link = admin_connection(config)
    try:
        with link.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS `{database}`')
        link.commit()
    finally:
        link.close()


def run_sql_file(config, database, filename):
    """Load schema.sql or seed.sql, rewriting the database name."""
    sql = (ROOT / filename).read_text().replace('car_rental', database)
    link = admin_connection(config)
    delimiter = ';'
    buffer = []
    try:
        with link.cursor() as cur:
            for line in sql.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith('--'):
                    continue
                if stripped.upper().startswith('DELIMITER '):
                    delimiter = stripped.split(None, 1)[1]
                    continue

                buffer.append(line)
                if not stripped.endswith(delimiter):
                    continue

                statement = '\n'.join(buffer).strip()
                statement = statement[:-len(delimiter)].strip()
                if statement:
                    cur.execute(statement)
                buffer = []

            if buffer:
                statement = '\n'.join(buffer).strip()
                if statement:
                    cur.execute(statement)
        link.commit()
    finally:
        link.close()


def reset_database(config, database):
    """Give each test a clean schema plus seed data."""
    drop_database(config, database)
    run_sql_file(config, database, 'schema.sql')
    run_sql_file(config, database, 'seed.sql')


def create_accounts(config, accounts):
    """Insert login rows: (email, role, customer_id, driver_id)."""
    link = _connect(config)
    try:
        with link.cursor() as cur:
            cur.executemany(
                """INSERT INTO USER_ACCOUNT
                   (Email, Password_Hash, Role, Customer_ID, Driver_ID)
                   VALUES (%s, %s, %s, %s, %s)""",
                [
                    (email, PASSWORD_HASH, role, customer_id, driver_id)
                    for email, role, customer_id, driver_id in accounts
                ],
            )
        link.commit()
    finally:
        link.close()


def fetchone(config, sql, params=()):
    link = _connect(config)
    try:
        with link.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    finally:
        link.close()
