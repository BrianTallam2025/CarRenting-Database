import os

import pymysql
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()
db = pymysql.connect(
    host=os.getenv('DB_HOST'),
    port=int(os.getenv('DB_PORT', 3306)),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'),
)

pw = generate_password_hash('demo1234')
accounts = [
    ('customer@example.com', 'customer', 1, None),
    ('agent@example.com', 'rental_agent', None, None),
    ('manager@example.com', 'fleet_manager', None, None),
    ('driver@example.com', 'driver', None, 1),
]

with db.cursor() as cur:
    for email, role, cust, drv in accounts:
        cur.execute(
            'INSERT IGNORE INTO USER_ACCOUNT (Email, Password_Hash, Role, Customer_ID, Driver_ID) '
            'VALUES (%s, %s, %s, %s, %s)', (email, pw, role, cust, drv))
db.commit()
print('Accounts created.')
