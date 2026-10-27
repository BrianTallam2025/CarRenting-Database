import os
import unittest
from datetime import date, timedelta
from pathlib import Path

import pymysql
from werkzeug.security import generate_password_hash

# Route tests get their own database. They never touch the demo `car_rental` DB.
TEST_DB = 'car_rental_b1_test'
os.environ['DB_NAME'] = TEST_DB

from app import create_app  # noqa: E402
from app.config import DB_CONFIG  # noqa: E402

DB_CONFIG['database'] = TEST_DB
ROOT = Path(__file__).resolve().parents[1]
PASSWORD_HASH = generate_password_hash('demo1234')

ACCOUNTS = [
    ('customer@example.com', 'customer', 1, None),
    ('agent@example.com', 'rental_agent', None, None),
    ('manager@example.com', 'fleet_manager', None, None),
    ('driver@example.com', 'driver', None, 1),
    ('driver2@example.com', 'driver', None, 2),
]


def _admin_connection():
    config = dict(DB_CONFIG)
    config.pop('database', None)
    return pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **config)


def _drop_database():
    connection = _admin_connection()
    try:
        with connection.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS `{TEST_DB}`')
        connection.commit()
    finally:
        connection.close()


def _run_sql_file(filename):
    sql = (ROOT / filename).read_text().replace('car_rental', TEST_DB)
    connection = _admin_connection()
    delimiter = ';'
    buffer = []
    try:
        with connection.cursor() as cur:
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
        connection.commit()
    finally:
        connection.close()


def _create_accounts():
    connection = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **DB_CONFIG)
    try:
        with connection.cursor() as cur:
            cur.executemany(
                """INSERT INTO USER_ACCOUNT
                   (Email, Password_Hash, Role, Customer_ID, Driver_ID)
                   VALUES (%s, %s, %s, %s, %s)""",
                [
                    (email, PASSWORD_HASH, role, customer_id, driver_id)
                    for email, role, customer_id, driver_id in ACCOUNTS
                ],
            )
        connection.commit()
    finally:
        connection.close()


def _fetchone(sql, params=()):
    connection = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **DB_CONFIG)
    try:
        with connection.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    finally:
        connection.close()


class B1RouteTests(unittest.TestCase):
    def setUp(self):
        _drop_database()
        _run_sql_file('schema.sql')
        _run_sql_file('seed.sql')
        _create_accounts()
        self.app = create_app({
            'TESTING': True,
            'WTF_CSRF_ENABLED': False,
            'SECRET_KEY': 'test',
        })
        self.client = self.app.test_client()

    @classmethod
    def tearDownClass(cls):
        _drop_database()

    def login(self, email, password='demo1234'):
        return self.client.post(
            '/login',
            data={'email': email, 'password': password},
        )

    def assert_page(self, path, *markers):
        response = self.client.get(path)
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200, path)
        for marker in markers:
            self.assertIn(marker, body, f'{marker!r} missing from {path}')

    def test_public_routes_and_bad_login(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Drive what fits the trip.', response.get_data(as_text=True))

        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Log in', response.get_data(as_text=True))

        response = self.client.get('/register')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Register', response.get_data(as_text=True))

        response = self.client.post(
            '/login',
            data={'email': 'customer@example.com', 'password': 'wrong-password'},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('Wrong email or password', response.get_data(as_text=True))

        response = self.client.get('/no-such-page')
        self.assertEqual(response.status_code, 404)
        self.assertIn('We could not find that page.', response.get_data(as_text=True))

    def test_login_redirects_each_role_to_its_home(self):
        homes = {
            'customer@example.com': '/customer',
            'agent@example.com': '/agent',
            'manager@example.com': '/fleet',
            'driver@example.com': '/driver',
        }
        for email, home in homes.items():
            with self.subTest(email=email):
                _drop_database()
                _run_sql_file('schema.sql')
                _run_sql_file('seed.sql')
                _create_accounts()
                client = self.app.test_client()
                response = client.post(
                    '/login',
                    data={'email': email, 'password': 'demo1234'},
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers['Location'], home)

    def test_customer_pages(self):
        self.login('customer@example.com')
        for path, markers in [
            ('/customer', ('Amina', 'My rentals')),
            ('/vehicles', ('Corolla', 'KES')),
            ('/vehicles/1', ('Rent this car', 'KDA 101A')),
            ('/rent/1', ('Estimated total',)),
            ('/rentals/1/confirmation', ('Rental confirmed', 'KDA 101A')),
            ('/my-rentals', ('Corolla', 'returned')),
            ('/profile', ('My profile', 'Amina')),
        ]:
            with self.subTest(path=path):
                self.assert_page(path, *markers)

        # A customer may not open another customer's confirmation page.
        response = self.client.get('/rentals/2/confirmation')
        self.assertEqual(response.status_code, 404)

    def test_driver_pages_and_driver_scoping(self):
        self.login('driver@example.com')
        self.assert_page(
            '/driver',
            'My current assignment',
            'Honda Civic',
            'Brian',
            'Otieno',
            '+254722000222',
        )
        self.assert_page('/driver/history', 'Trip history', 'Corolla')

        # Driver 2 has no job; driver 1's Honda job must not leak into this view.
        self.client.get('/logout')
        self.login('driver2@example.com')
        self.assert_page('/driver', 'No current assignment')
        self.assert_page('/driver/history', 'No completed trips yet.')
        response = self.client.get('/driver')
        self.assertNotIn('Honda Civic', response.get_data(as_text=True))

    def test_agent_pages(self):
        self.login('agent@example.com')
        for path, markers in [
            ('/agent', ('Active rentals', 'Overdue rentals')),
            ('/agent/rentals', ('Brian', 'overdue')),
            ('/agent/rentals/2', ('Honda Civic', 'James')),
            ('/agent/rentals/2/return', ('Days late', '13500')),
            ('/agent/rentals/2/assign-driver', ('Assign driver', 'Peter')),
            ('/agent/customers?selected=2', ('Brian',)),
            ('/agent/rent', ('Walk-in',)),
        ]:
            with self.subTest(path=path):
                self.assert_page(path, *markers)

    def test_manager_pages(self):
        self.login('manager@example.com')
        for path, markers in [
            ('/fleet', ('Fleet dashboard', 'KDC 303C')),
            ('/fleet/vehicles', ('Corolla',)),
            ('/fleet/vehicles/new', ('Add car',)),
            ('/fleet/vehicles/1/edit', ('Edit car',)),
            ('/fleet/insurance', ('Insurance',)),
            ('/fleet/maintenance', ('Maintenance', 'Complete')),
            ('/fleet/maintenance/new', ('Schedule maintenance',)),
            ('/fleet/drivers', ('Drivers', 'James')),
            ('/fleet/drivers/new', ('Add driver',)),
            ('/fleet/drivers/1/edit', ('Edit driver',)),
            ('/fleet/assignment-history', ('Assignment history',)),
            ('/fleet/rentals/2/reassign', ('Change car or driver',)),
            ('/agent/rentals/2', ('Change car or driver',)),
        ]:
            with self.subTest(path=path):
                self.assert_page(path, *markers)

    def test_role_blocks(self):
        self.login('customer@example.com')
        for path in ('/driver', '/agent', '/fleet'):
            with self.subTest(role='customer', path=path):
                self.assertEqual(self.client.get(path).status_code, 403)
        self.client.get('/logout')

        self.login('driver@example.com')
        for path in ('/customer', '/agent', '/fleet'):
            with self.subTest(role='driver', path=path):
                self.assertEqual(self.client.get(path).status_code, 403)
        self.client.get('/logout')

        self.login('agent@example.com')
        for path in ('/customer', '/fleet', '/driver'):
            with self.subTest(role='agent', path=path):
                self.assertEqual(self.client.get(path).status_code, 403)
        self.client.get('/logout')

        self.login('manager@example.com')
        for path in ('/customer', '/driver'):
            with self.subTest(role='manager', path=path):
                self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.get('/agent').status_code, 403)

        # Logged-out users are sent to login, not given a 403.
        self.client.get('/logout')
        response = self.client.get('/customer')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers['Location'])

    def test_agent_assign_and_manager_reassign(self):
        self.login('agent@example.com')
        response = self.client.post(
            '/agent/rentals/2/assign-driver',
            data={'driver_id': '2'},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('Driver assigned.', response.get_data(as_text=True))

        rental = _fetchone(
            'SELECT Vehicle_ID, Driver_ID FROM RENTAL WHERE Rental_ID = 2'
        )
        self.assertEqual(rental['Driver_ID'], 2)
        self.assertEqual(
            _fetchone('SELECT Status FROM DRIVER WHERE Driver_ID = 1')['Status'],
            'available',
        )
        self.assertEqual(
            _fetchone('SELECT Status FROM DRIVER WHERE Driver_ID = 2')['Status'],
            'assigned',
        )

        self.client.get('/logout')
        self.login('manager@example.com')
        response = self.client.post(
            '/fleet/rentals/2/reassign',
            data={
                'vehicle_id': '4',
                'driver_id': '3',
                'reason': 'Route test reassign',
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('Change saved.', response.get_data(as_text=True))

        rental = _fetchone(
            'SELECT Vehicle_ID, Driver_ID FROM RENTAL WHERE Rental_ID = 2'
        )
        self.assertEqual((rental['Vehicle_ID'], rental['Driver_ID']), (4, 3))
        for vehicle_id, status in ((2, 'available'), (4, 'rented')):
            self.assertEqual(
                _fetchone(
                    'SELECT Status FROM VEHICLE WHERE Vehicle_ID = %s',
                    (vehicle_id,),
                )['Status'],
                status,
            )
        for driver_id, status in ((2, 'available'), (3, 'assigned')):
            self.assertEqual(
                _fetchone(
                    'SELECT Status FROM DRIVER WHERE Driver_ID = %s',
                    (driver_id,),
                )['Status'],
                status,
            )
        history = _fetchone(
            """SELECT Rental_ID, Old_Vehicle_ID, New_Vehicle_ID,
                      Old_Driver_ID, New_Driver_ID, Reason
               FROM ASSIGNMENT_HISTORY"""
        )
        self.assertEqual(
            (
                history['Rental_ID'],
                history['Old_Vehicle_ID'],
                history['New_Vehicle_ID'],
                history['Old_Driver_ID'],
                history['New_Driver_ID'],
                history['Reason'],
            ),
            (2, 2, 4, 2, 3, 'Route test reassign'),
        )

        # Returning the reassigned rental clears the new car and driver.
        self.client.get('/logout')
        self.login('agent@example.com')
        response = self.client.post(
            '/agent/rentals/2/return',
            data={'return_date': date.today().isoformat()},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('Return processed.', response.get_data(as_text=True))
        rental = _fetchone(
            """SELECT Return_Date, Late_Fee
               FROM RENTAL WHERE Rental_ID = 2"""
        )
        self.assertEqual(rental['Return_Date'], date.today())
        self.assertEqual(rental['Late_Fee'], 27000)
        self.assertEqual(
            _fetchone('SELECT Status FROM VEHICLE WHERE Vehicle_ID = 4')['Status'],
            'available',
        )
        self.assertEqual(
            _fetchone('SELECT Status FROM DRIVER WHERE Driver_ID = 3')['Status'],
            'available',
        )

    def test_walkin_customer_can_link_login(self):
        self.login('agent@example.com')
        start = date.today() + timedelta(days=1)
        end = start + timedelta(days=2)
        response = self.client.post(
            '/agent/rent',
            data={
                'first_name': 'Walkin',
                'last_name': 'Route',
                'email': 'walkin.route@example.com',
                'national_id': 'ROUTE-ID-001',
                'license_number': 'ROUTE-LIC-001',
                'license_expiry': '2029-01-01',
                'vehicle_id': '1',
                'start_date': start.isoformat(),
                'end_date': end.isoformat(),
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('Rental created.', response.get_data(as_text=True))

        customer = _fetchone(
            'SELECT Customer_ID FROM CUSTOMER WHERE Email = %s',
            ('walkin.route@example.com',),
        )
        self.assertIsNotNone(customer)

        client = self.app.test_client()
        response = client.post(
            '/register',
            data={
                'first_name': 'Walkin',
                'last_name': 'Route',
                'email': 'walkin.route@example.com',
                'password': 'demo1234',
                'national_id': 'ROUTE-ID-001',
                'license_number': 'ROUTE-LIC-001',
                'license_expiry': '2029-01-01',
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('linked to your login', response.get_data(as_text=True))

        # The login points at the existing customer, not a duplicate record.
        account = _fetchone(
            'SELECT Customer_ID FROM USER_ACCOUNT WHERE Email = %s',
            ('walkin.route@example.com',),
        )
        self.assertEqual(account['Customer_ID'], customer['Customer_ID'])
        customers = _fetchone(
            'SELECT COUNT(*) AS total FROM CUSTOMER WHERE Email = %s',
            ('walkin.route@example.com',),
        )
        self.assertEqual(customers['total'], 1)

        response = client.get('/my-rentals')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Corolla', response.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
