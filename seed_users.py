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

try:
    with db.cursor() as cur:
        for email, role, customer_id, driver_id in accounts:
            cur.execute(
                'INSERT INTO USER_ACCOUNT '
                '(Email, Password_Hash, Role, Customer_ID, Driver_ID) '
                'VALUES (%s, %s, %s, %s, %s) '
                'ON DUPLICATE KEY UPDATE Password_Hash = %s, Role = %s, '
                'Customer_ID = %s, Driver_ID = %s',
                (
                    email,
                    pw,
                    role,
                    customer_id,
                    driver_id,
                    pw,
                    role,
                    customer_id,
                    driver_id,
                ),
            )
    db.commit()
    print('Accounts created.')
except Exception:
    db.rollback()
    raise
finally:
    db.close()
