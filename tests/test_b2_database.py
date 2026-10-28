import os
import unittest
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pymysql
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import DB_CONFIG

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = f"car_rental_b2_test_{uuid.uuid4().hex[:12]}"
TEST_PASSWORD = 'b2-test-password'


@unittest.skipUnless(
    os.getenv('RUN_MYSQL_TESTS') == '1',
    'Set RUN_MYSQL_TESTS=1 to run tests against an isolated MySQL database.',
)
class B2DatabaseRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_name = TEST_DB
        cls.db_config = dict(DB_CONFIG, database=cls.database_name)
        cls.db_config_patcher = patch.dict(
            'app.db.DB_CONFIG',
            {'database': cls.database_name},
        )
        cls.db_config_patcher.start()
        cls.addClassCleanup(cls.db_config_patcher.stop)
        cls.app = create_app(
            {
                'TESTING': True,
                'WTF_CSRF_ENABLED': False,
                'SECRET_KEY': 'b2-test-secret',
            }
        )
        cls.create_test_database()
        cls.addClassCleanup(cls.drop_test_database)
        cls.reset_database()

    @classmethod
    def admin_connection(cls):
        config = dict(cls.db_config)
        config.pop('database', None)
        return pymysql.connect(**config)

    @classmethod
    def drop_test_database(cls):
        connection = cls.admin_connection()
        try:
            with connection.cursor() as cur:
                cur.execute(f'DROP DATABASE IF EXISTS `{cls.database_name}`')
        finally:
            connection.close()

    @classmethod
    def create_test_database(cls):
        connection = cls.admin_connection()
        try:
            with connection.cursor() as cur:
                cur.execute(f'CREATE DATABASE `{cls.database_name}`')
        finally:
            connection.close()

    @classmethod
    def run_sql_file(cls, filename):
        sql = (ROOT / filename).read_text(encoding='utf-8')
        sql = sql.replace('car_rental', cls.database_name)
        connection = cls.admin_connection()
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

    @classmethod
    def reset_database(cls):
        cls.drop_test_database()
        cls.create_test_database()

        cls.run_sql_file('schema.sql')
        cls.run_sql_file('seed.sql')
        connection = pymysql.connect(
            cursorclass=pymysql.cursors.DictCursor,
            **cls.db_config,
        )
        password_hash = generate_password_hash(TEST_PASSWORD)
        try:
            with connection.cursor() as cur:
                cur.executemany(
                    """INSERT INTO USER_ACCOUNT
                       (Email, Password_Hash, Role, Customer_ID, Driver_ID)
                       VALUES (%s, %s, %s, %s, %s)""",
                    [
                        (
                            'b2-customer@example.com',
                            password_hash,
                            'customer',
                            1,
                            None,
                        ),
                        (
                            'b2-agent@example.com',
                            password_hash,
                            'rental_agent',
                            None,
                            None,
                        ),
                        (
                            'b2-manager@example.com',
                            password_hash,
                            'fleet_manager',
                            None,
                            None,
                        ),
                    ],
                )
            connection.commit()
        finally:
            connection.close()

    def setUp(self):
        self.reset_database()
        self.client = self.app.test_client()

    def connect(self):
        return pymysql.connect(
            cursorclass=pymysql.cursors.DictCursor,
            **self.db_config,
        )

    def fetchone(self, sql, params=()):
        connection = self.connect()
        try:
            with connection.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()
        finally:
            connection.close()

    def execute(self, sql, params=()):
        connection = self.connect()
        try:
            with connection.cursor() as cur:
                cur.execute(sql, params)
            connection.commit()
        finally:
            connection.close()

    def login(self, role):
        response = self.client.post(
            '/login',
            data={
                'email': f'b2-{role}@example.com',
                'password': TEST_PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 302)

    def add_rental(self, customer_id=1, vehicle_id=1, due_date=None, driver_id=None):
        due_date = due_date or date.today() + timedelta(days=2)
        rental_date = min(date.today(), due_date)
        connection = self.connect()
        try:
            with connection.cursor() as cur:
                cur.execute(
                    """INSERT INTO RENTAL
                       (Customer_ID, Vehicle_ID, Driver_ID, Is_Chauffeur,
                        Rental_Date, Due_Date, Total_Cost)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        customer_id,
                        vehicle_id,
                        driver_id,
                        driver_id is not None,
                        rental_date,
                        due_date,
                        Decimal('9975.00'),
                    ),
                )
                rental_id = cur.lastrowid
            connection.commit()
            return rental_id
        finally:
            connection.close()

    def add_completed_rentals(self, count, customer_id=1):
        connection = self.connect()
        try:
            with connection.cursor() as cur:
                for index in range(count):
                    due_date = date.today() - timedelta(days=index + 10)
                    cur.execute(
                        """INSERT INTO RENTAL
                           (Customer_ID, Vehicle_ID, Rental_Date, Due_Date,
                            Return_Date, Total_Cost)
                           VALUES (%s, 1, %s, %s, %s, %s)""",
                        (
                            customer_id,
                            due_date - timedelta(days=2),
                            due_date,
                            due_date,
                            Decimal('100.00'),
                        ),
                    )
            connection.commit()
        finally:
            connection.close()

    def test_r1_duplicate_vin_and_plate_are_rejected(self):
        for column, value in (
            ('VIN', 'JTDBR32E730123456'),
            ('Plate_Number', 'KDA 101A'),
        ):
            with self.subTest(column=column):
                connection = self.connect()
                try:
                    with connection.cursor() as cur:
                        with self.assertRaises(pymysql.err.IntegrityError):
                            cur.execute(
                                f"""INSERT INTO VEHICLE
                                    (VIN, Plate_Number, Make, Model, Year, Daily_Rate)
                                    VALUES (%s, %s, 'Test', 'Duplicate', 2025, 1000)""",
                                (
                                    value if column == 'VIN' else 'TESTVIN000000000',
                                    value if column == 'Plate_Number' else 'TEST 999Z',
                                ),
                            )
                finally:
                    connection.rollback()
                    connection.close()

    def test_r2_expired_customer_license_blocks_rental(self):
        self.execute(
            'UPDATE CUSTOMER SET License_Expiry = %s WHERE Customer_ID = 1',
            (date.today() - timedelta(days=1),),
        )
        before = self.fetchone('SELECT COUNT(*) AS count FROM RENTAL')['count']
        self.login('customer')
        response = self.client.post(
            '/rent/1',
            data={
                'start_date': date.today().isoformat(),
                'end_date': (date.today() + timedelta(days=2)).isoformat(),
            },
            follow_redirects=True,
        )
        self.assertIn('Your driving license has expired', response.get_data(as_text=True))
        self.assertEqual(self.fetchone('SELECT COUNT(*) AS count FROM RENTAL')['count'], before)

    def test_r3_expired_insurance_blocks_rental(self):
        self.execute(
            'UPDATE INSURANCE_POLICY SET Expiry_Date = %s WHERE Vehicle_ID = 1',
            (date.today() - timedelta(days=1),),
        )
        before = self.fetchone('SELECT COUNT(*) AS count FROM RENTAL')['count']
        self.login('customer')
        response = self.client.post(
            '/rent/1',
            data={
                'start_date': date.today().isoformat(),
                'end_date': (date.today() + timedelta(days=2)).isoformat(),
            },
            follow_redirects=True,
        )
        self.assertIn('Vehicle not available', response.get_data(as_text=True))
        self.assertEqual(self.fetchone('SELECT COUNT(*) AS count FROM RENTAL')['count'], before)

    def test_r3_rented_vehicle_blocks_rental(self):
        before = self.fetchone('SELECT COUNT(*) AS count FROM RENTAL')['count']
        self.login('customer')
        response = self.client.post(
            '/rent/2',
            data={
                'start_date': date.today().isoformat(),
                'end_date': (date.today() + timedelta(days=2)).isoformat(),
            },
            follow_redirects=True,
        )
        self.assertIn('Vehicle not available', response.get_data(as_text=True))
        self.assertEqual(self.fetchone('SELECT COUNT(*) AS count FROM RENTAL')['count'], before)

    def test_r4_existing_active_maintenance_blocks_scheduling(self):
        before = self.fetchone('SELECT COUNT(*) AS count FROM MAINTENANCE')['count']
        self.login('manager')
        response = self.client.post(
            '/fleet/maintenance/new',
            data={
                'vehicle_id': '5',
                'start_date': date.today().isoformat(),
                'description': 'Duplicate active maintenance',
            },
            follow_redirects=True,
        )
        self.assertIn(
            'already has scheduled or active maintenance',
            response.get_data(as_text=True),
        )
        current = self.fetchone('SELECT COUNT(*) AS count FROM MAINTENANCE')['count']
        self.assertEqual(current, before)

    def test_r4_rented_vehicle_cannot_be_scheduled_for_maintenance(self):
        before = self.fetchone('SELECT COUNT(*) AS count FROM MAINTENANCE')['count']
        self.login('manager')
        response = self.client.post(
            '/fleet/maintenance/new',
            data={
                'vehicle_id': '2',
                'start_date': date.today().isoformat(),
                'description': 'Maintenance for rented vehicle',
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        current = self.fetchone('SELECT COUNT(*) AS count FROM MAINTENANCE')['count']
        self.assertEqual(current, before)

    def test_r4_maintenance_start_and_completion_update_vehicle_status(self):
        self.login('manager')
        response = self.client.post(
            '/fleet/maintenance/new',
            data={
                'vehicle_id': '4',
                'start_date': date.today().isoformat(),
                'description': 'B2 maintenance transition test',
            },
            follow_redirects=True,
        )
        self.assertIn('Maintenance scheduled.', response.get_data(as_text=True))
        job_id = self.fetchone(
            """SELECT Maintenance_ID FROM MAINTENANCE
               WHERE Vehicle_ID = 4 ORDER BY Maintenance_ID DESC LIMIT 1"""
        )['Maintenance_ID']

        response = self.client.post(
            f'/fleet/maintenance/{job_id}/start',
            follow_redirects=True,
        )
        self.assertIn('Maintenance started.', response.get_data(as_text=True))
        self.assertEqual(
            self.fetchone('SELECT Status FROM VEHICLE WHERE Vehicle_ID = 4')['Status'],
            'maintenance',
        )

        response = self.client.post(
            f'/fleet/maintenance/{job_id}/complete',
            follow_redirects=True,
        )
        self.assertIn('Maintenance completed.', response.get_data(as_text=True))
        self.assertEqual(
            self.fetchone(
                'SELECT Status, End_Date FROM MAINTENANCE WHERE Maintenance_ID = %s',
                (job_id,),
            ),
            {'Status': 'completed', 'End_Date': date.today()},
        )
        self.assertEqual(
            self.fetchone('SELECT Status FROM VEHICLE WHERE Vehicle_ID = 4')['Status'],
            'available',
        )

    def test_r5_driver_with_open_rental_cannot_be_assigned(self):
        rental_id = self.add_rental()
        self.login('agent')
        response = self.client.post(
            f'/agent/rentals/{rental_id}/assign-driver',
            data={'driver_id': '1'},
            follow_redirects=True,
        )
        self.assertIn('Driver is not available', response.get_data(as_text=True))
        rental = self.fetchone(
            'SELECT Driver_ID FROM RENTAL WHERE Rental_ID = %s',
            (rental_id,),
        )
        self.assertIsNone(rental['Driver_ID'])

    def test_r6_two_days_late_saves_expected_fee_and_releases_car(self):
        rental_id = self.add_rental(due_date=date.today() - timedelta(days=2))
        self.login('agent')
        response = self.client.post(
            f'/agent/rentals/{rental_id}/return',
            data={'return_date': date.today().isoformat()},
            follow_redirects=True,
        )
        self.assertIn('Late fee: 10500.00', response.get_data(as_text=True))
        rental = self.fetchone(
            'SELECT Return_Date, Late_Fee FROM RENTAL WHERE Rental_ID = %s',
            (rental_id,),
        )
        self.assertEqual(rental['Return_Date'], date.today())
        self.assertEqual(rental['Late_Fee'], Decimal('10500.00'))
        self.assertEqual(
            self.fetchone('SELECT Status FROM VEHICLE WHERE Vehicle_ID = 1')['Status'],
            'available',
        )

    def test_rental_return_does_not_clear_active_maintenance_status(self):
        rental_id = self.add_rental(vehicle_id=5, due_date=date.today())
        self.login('agent')
        response = self.client.post(
            f'/agent/rentals/{rental_id}/return',
            data={'return_date': date.today().isoformat()},
            follow_redirects=True,
        )
        self.assertIn('Return processed.', response.get_data(as_text=True))
        self.assertEqual(
            self.fetchone('SELECT Status FROM VEHICLE WHERE Vehicle_ID = 5')['Status'],
            'maintenance',
        )

    def test_r7_fifth_completed_rental_sets_silver_tier(self):
        self.add_completed_rentals(3)
        rental_id = self.add_rental(due_date=date.today())
        self.login('agent')
        response = self.client.post(
            f'/agent/rentals/{rental_id}/return',
            data={'return_date': date.today().isoformat()},
            follow_redirects=True,
        )
        self.assertIn('Return processed.', response.get_data(as_text=True))
        self.assertEqual(
            self.fetchone('SELECT Tier FROM CUSTOMER WHERE Customer_ID = 1')['Tier'],
            'silver',
        )

    def test_r7_tenth_completed_rental_sets_gold_tier(self):
        self.add_completed_rentals(8)
        rental_id = self.add_rental(due_date=date.today())
        self.login('agent')
        response = self.client.post(
            f'/agent/rentals/{rental_id}/return',
            data={'return_date': date.today().isoformat()},
            follow_redirects=True,
        )
        self.assertIn('Return processed.', response.get_data(as_text=True))
        self.assertEqual(
            self.fetchone('SELECT Tier FROM CUSTOMER WHERE Customer_ID = 1')['Tier'],
            'gold',
        )

    def test_r8_silver_late_return_fee_has_no_discount(self):
        self.add_completed_rentals(3)
        rental_id = self.add_rental(due_date=date.today() - timedelta(days=2))
        self.login('agent')
        response = self.client.post(
            f'/agent/rentals/{rental_id}/return',
            data={'return_date': date.today().isoformat()},
            follow_redirects=True,
        )
        self.assertIn('Late fee: 10500.00', response.get_data(as_text=True))
        self.assertEqual(
            self.fetchone(
                'SELECT Late_Fee FROM RENTAL WHERE Rental_ID = %s',
                (rental_id,),
            )['Late_Fee'],
            Decimal('10500.00'),
        )
        self.assertEqual(
            self.fetchone('SELECT Tier FROM CUSTOMER WHERE Customer_ID = 1')['Tier'],
            'silver',
        )

    def test_r9_deleting_vehicle_preserves_rental_with_null_vehicle(self):
        self.execute('DELETE FROM INSURANCE_POLICY WHERE Vehicle_ID = 1')
        self.execute('DELETE FROM VEHICLE WHERE Vehicle_ID = 1')
        rental = self.fetchone('SELECT Rental_ID, Vehicle_ID FROM RENTAL WHERE Rental_ID = 1')
        self.assertEqual(rental['Rental_ID'], 1)
        self.assertIsNone(rental['Vehicle_ID'])

    def test_r10_uninsured_reassignment_is_rejected_without_history(self):
        self.execute('DELETE FROM INSURANCE_POLICY WHERE Vehicle_ID = 4')
        self.login('manager')
        response = self.client.post(
            '/fleet/rentals/2/reassign',
            data={
                'vehicle_id': '4',
                'driver_id': '3',
                'reason': 'Test uninsured reassignment',
            },
            follow_redirects=True,
        )
        self.assertIn('Vehicle not available', response.get_data(as_text=True))
        self.assertEqual(
            self.fetchone(
                'SELECT Vehicle_ID FROM RENTAL WHERE Rental_ID = 2'
            )['Vehicle_ID'],
            2,
        )
        self.assertEqual(
            self.fetchone('SELECT COUNT(*) AS count FROM ASSIGNMENT_HISTORY')['count'],
            0,
        )

    def test_r10_valid_reassignment_adds_one_history_row(self):
        self.login('manager')
        response = self.client.post(
            '/fleet/rentals/2/reassign',
            data={
                'vehicle_id': '4',
                'driver_id': '3',
                'reason': 'Test valid reassignment',
            },
            follow_redirects=True,
        )
        self.assertIn('Change saved.', response.get_data(as_text=True))
        self.assertEqual(
            self.fetchone(
                'SELECT Vehicle_ID, Driver_ID FROM RENTAL WHERE Rental_ID = 2'
            ),
            {'Vehicle_ID': 4, 'Driver_ID': 3},
        )
        history = self.fetchone(
            'SELECT Rental_ID, Old_Vehicle_ID, New_Vehicle_ID, Reason '
            'FROM ASSIGNMENT_HISTORY'
        )
        self.assertEqual(
            history,
            {
                'Rental_ID': 2,
                'Old_Vehicle_ID': 2,
                'New_Vehicle_ID': 4,
                'Reason': 'Test valid reassignment',
            },
        )

    def test_fleet_vehicle_driver_and_insurance_forms_persist_changes(self):
        self.login('manager')
        response = self.client.post(
            '/fleet/vehicles/new',
            data={
                'vin': 'B2TEST00000000001',
                'plate_number': 'B2T 123A',
                'make': 'Test',
                'model': 'Rental',
                'year': '2024',
                'daily_rate': '5200.00',
            },
            follow_redirects=True,
        )
        self.assertIn('Vehicle added.', response.get_data(as_text=True))
        vehicle = self.fetchone(
            "SELECT Vehicle_ID FROM VEHICLE WHERE VIN = 'B2TEST00000000001'"
        )
        self.assertIsNotNone(vehicle)
        response = self.client.post(
            f"/fleet/vehicles/{vehicle['Vehicle_ID']}/edit",
            data={
                'vin': 'B2TEST00000000001',
                'plate_number': 'B2T 123A',
                'make': 'Updated',
                'model': 'Rental',
                'year': '2025',
                'daily_rate': '5300.00',
            },
            follow_redirects=True,
        )
        self.assertIn('Vehicle updated.', response.get_data(as_text=True))
        self.assertEqual(
            self.fetchone(
                'SELECT Make, Daily_Rate FROM VEHICLE WHERE Vehicle_ID = %s',
                (vehicle['Vehicle_ID'],),
            ),
            {'Make': 'Updated', 'Daily_Rate': Decimal('5300.00')},
        )

        response = self.client.post(
            '/fleet/drivers/new',
            data={
                'first_name': 'B2',
                'last_name': 'Driver',
                'license_number': 'B2-DL-0001',
            },
            follow_redirects=True,
        )
        self.assertIn('Driver added.', response.get_data(as_text=True))
        driver = self.fetchone(
            "SELECT Driver_ID FROM DRIVER WHERE License_Number = 'B2-DL-0001'"
        )
        self.assertIsNotNone(driver)
        response = self.client.post(
            f"/fleet/drivers/{driver['Driver_ID']}/edit",
            data={
                'first_name': 'Updated',
                'last_name': 'Driver',
                'license_number': 'B2-DL-0001',
            },
            follow_redirects=True,
        )
        self.assertIn('Driver updated.', response.get_data(as_text=True))
        self.assertEqual(
            self.fetchone(
                'SELECT First_Name FROM DRIVER WHERE Driver_ID = %s',
                (driver['Driver_ID'],),
            )['First_Name'],
            'Updated',
        )

        response = self.client.post(
            '/fleet/insurance',
            data={
                'vehicle_id': '1',
                'provider': 'B2 Test Insurance',
                'expiry_date': (date.today() + timedelta(days=365)).isoformat(),
            },
            follow_redirects=True,
        )
        self.assertIn('Insurance policy saved.', response.get_data(as_text=True))
        self.assertEqual(
            self.fetchone(
                'SELECT Provider FROM INSURANCE_POLICY WHERE Vehicle_ID = 1'
            )['Provider'],
            'B2 Test Insurance',
        )


if __name__ == '__main__':
    unittest.main()
