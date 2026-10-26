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

try:
    with db.cursor() as cur:
        cur.execute(
            'SELECT Customer_ID FROM CUSTOMER WHERE National_ID = %s',
            ('DEMO-CUSTOMER-001',),
        )
        customer = cur.fetchone()
        if customer:
            customer_id = customer[0]
        else:
            cur.execute(
                'INSERT INTO CUSTOMER '
                '(National_ID, First_Name, Last_Name, Email, License_Number, License_Expiry) '
                'VALUES (%s, %s, %s, %s, %s, %s)',
                (
                    'DEMO-CUSTOMER-001',
                    'Demo',
                    'Customer',
                    'customer@demo.test',
                    'DEMO-LICENSE-001',
                    '2099-12-31',
                ),
            )
            customer_id = cur.lastrowid

        cur.execute(
            'SELECT Driver_ID FROM DRIVER WHERE License_Number = %s',
            ('DEMO-DRIVER-001',),
        )
        driver = cur.fetchone()
        if driver:
            driver_id = driver[0]
        else:
            cur.execute(
                'INSERT INTO DRIVER (First_Name, Last_Name, License_Number) '
                'VALUES (%s, %s, %s)',
                ('Demo', 'Driver', 'DEMO-DRIVER-001'),
            )
            driver_id = cur.lastrowid

        accounts = [
            ('customer@demo.test', 'customer', customer_id, None),
            ('agent@demo.test', 'rental_agent', None, None),
            ('manager@demo.test', 'fleet_manager', None, None),
            ('driver@demo.test', 'driver', None, driver_id),
        ]
        for email, role, cust, drv in accounts:
            cur.execute(
                'INSERT INTO USER_ACCOUNT '
                '(Email, Password_Hash, Role, Customer_ID, Driver_ID) '
                'VALUES (%s, %s, %s, %s, %s) '
                'ON DUPLICATE KEY UPDATE Password_Hash = %s, Role = %s, '
                'Customer_ID = %s, Driver_ID = %s',
                (email, pw, role, cust, drv, pw, role, cust, drv),
            )
    db.commit()
    print('Accounts created.')
except Exception:
    db.rollback()
    raise
finally:
    db.close()
