"""Database tests for the business rules R1-R10 in README section 16.

Every test runs against a throwaway copy of schema.sql + seed.sql, so the
demo `car_rental` database is never modified. The rules that live in the
schema (UNIQUE keys, the tier trigger, ON DELETE SET NULL) are exercised
with SQL; the rules that live in the app are exercised through the real
service functions and routes.
"""

import os
import sys
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pymysql

sys.path.insert(0, str(Path(__file__).resolve().parent))

TEST_DB = 'car_rental_rules_test'
os.environ['DB_NAME'] = TEST_DB

from app import create_app  # noqa: E402
from app.config import DB_CONFIG  # noqa: E402
from app.services.pricing import late_fee, total_cost  # noqa: E402
from app.services.rules import (  # noqa: E402
    customer_license_valid,
    has_active_maintenance,
    is_driver_free,
    is_vehicle_available,
)
from db_support import (  # noqa: E402
    create_accounts,
    drop_database,
    execute,
    fetchall,
    fetchone,
    reset_database,
)

ACCOUNTS = [
    ('customer@example.com', 'customer', 1, None),
    ('agent@example.com', 'rental_agent', None, None),
    ('manager@example.com', 'fleet_manager', None, None),
    ('driver@example.com', 'driver', None, 1),
]


class BusinessRuleTests(unittest.TestCase):
    def setUp(self):
        DB_CONFIG['database'] = TEST_DB
        reset_database(DB_CONFIG, TEST_DB)
        create_accounts(DB_CONFIG, ACCOUNTS)
        self.app = create_app({
            'TESTING': True,
            'WTF_CSRF_ENABLED': False,
            'SECRET_KEY': 'test',
        })
        self.client = self.app.test_client()

    @classmethod
    def tearDownClass(cls):
        drop_database(DB_CONFIG, TEST_DB)

    # helpers -------------------------------------------------------------

    def rule(self, check, *args):
        """Run a rule helper like a request would: on a fresh connection."""
        with self.app.app_context():
            return check(*args)

    def login(self, email):
        response = self.client.post(
            '/login', data={'email': email, 'password': 'demo1234'}
        )
        self.assertEqual(response.status_code, 302, email)
        return response

    def db_today(self):
        return fetchone(DB_CONFIG, 'SELECT CURDATE() AS today')['today']

    def count(self, sql, params=()):
        return fetchone(DB_CONFIG, sql, params)['total']

    def set_insurance_expired(self, vehicle_id):
        execute(
            DB_CONFIG,
            'UPDATE INSURANCE_POLICY SET Expiry_Date = %s WHERE Vehicle_ID = %s',
            (date.today() - timedelta(days=1), vehicle_id),
        )

    def add_open_rental(self, customer_id, driver_id):
        """Give a driver a second open job so R5 has something to catch."""
        return execute(
            DB_CONFIG,
            """INSERT INTO RENTAL
               (Customer_ID, Vehicle_ID, Driver_ID, Rental_Date, Due_Date, Total_Cost)
               VALUES (%s, NULL, %s, CURDATE(),
                       DATE_ADD(CURDATE(), INTERVAL 2 DAY), 1000.00)""",
            (customer_id, driver_id),
        )

    def add_returned_rental(self, customer_id):
        """Insert then close a rental so trg_update_tier fires."""
        rental_id = execute(
            DB_CONFIG,
            """INSERT INTO RENTAL
               (Customer_ID, Vehicle_ID, Rental_Date, Due_Date, Total_Cost)
               VALUES (%s, NULL, CURDATE(), CURDATE(), 1000.00)""",
            (customer_id,),
        )
        execute(
            DB_CONFIG,
            'UPDATE RENTAL SET Return_Date = CURDATE() WHERE Rental_ID = %s',
            (rental_id,),
        )
        return rental_id

    # R1 ------------------------------------------------------------------

    def test_r1_vin_and_plate_must_be_unique(self):
        insert = """INSERT INTO VEHICLE
                    (VIN, Plate_Number, Make, Model, Year, Daily_Rate)
                    VALUES (%s, %s, 'Toyota', 'Corolla', 2024, 3500.00)"""

        with self.assertRaises(pymysql.err.IntegrityError):
            execute(DB_CONFIG, insert, ('JTDBR32E730123456', 'KDA 999Z'))

        with self.assertRaises(pymysql.err.IntegrityError):
            execute(DB_CONFIG, insert, ('1NEWVIN0000000001', 'KDA 101A'))

        self.assertEqual(self.count('SELECT COUNT(*) AS total FROM VEHICLE'), 5)
        # The same VIN and plate against a fresh car are accepted.
        execute(DB_CONFIG, insert, ('1NEWVIN0000000001', 'KDA 999Z'))
        self.assertEqual(self.count('SELECT COUNT(*) AS total FROM VEHICLE'), 6)

    # R2 ------------------------------------------------------------------

    def test_r2_expired_licence_blocks_a_rental(self):
        self.assertTrue(self.rule(customer_license_valid, 1))
        execute(
            DB_CONFIG,
            'UPDATE CUSTOMER SET License_Expiry = %s WHERE Customer_ID = 1',
            (date.today() - timedelta(days=1),),
        )
        self.assertFalse(self.rule(customer_license_valid, 1))

        self.login('customer@example.com')
        start = date.today() + timedelta(days=1)
        response = self.client.post(
            '/rent/1',
            data={
                'start_date': start.isoformat(),
                'end_date': (start + timedelta(days=2)).isoformat(),
            },
            follow_redirects=True,
        )
        self.assertIn('driving license has expired', response.get_data(as_text=True))
        self.assertEqual(self.count('SELECT COUNT(*) AS total FROM RENTAL'), 3)
        self.assertEqual(
            fetchone(
                DB_CONFIG, 'SELECT Status FROM VEHICLE WHERE Vehicle_ID = 1'
            )['Status'],
            'available',
        )

    # R3 ------------------------------------------------------------------

    def test_r3_car_must_be_available_and_insured(self):
        self.assertTrue(self.rule(is_vehicle_available, 1))
        self.assertFalse(self.rule(is_vehicle_available, 2), 'rented car')
        self.assertFalse(self.rule(is_vehicle_available, 5), 'car in maintenance')

        self.set_insurance_expired(1)
        self.assertFalse(self.rule(is_vehicle_available, 1), 'expired policy')

        self.login('customer@example.com')
        start = date.today() + timedelta(days=1)
        response = self.client.post(
            '/rent/1',
            data={
                'start_date': start.isoformat(),
                'end_date': (start + timedelta(days=2)).isoformat(),
            },
            follow_redirects=True,
        )
        self.assertIn('Vehicle not available', response.get_data(as_text=True))
        self.assertEqual(self.count('SELECT COUNT(*) AS total FROM RENTAL'), 3)

    # R4 ------------------------------------------------------------------

    def test_r4_maintenance_conflicts(self):
        # Vehicle 5 already has an in_progress job.
        self.assertTrue(self.rule(has_active_maintenance, 5))

        self.login('manager@example.com')
        response = self.client.post(
            '/fleet/maintenance/new',
            data={
                'vehicle_id': '5',
                'start_date': date.today().isoformat(),
                'end_date': '',
                'description': 'Second job on the same car',
            },
            follow_redirects=True,
        )
        self.assertIn(
            'already has scheduled or active maintenance',
            response.get_data(as_text=True),
        )
        self.assertEqual(
            self.count(
                'SELECT COUNT(*) AS total FROM MAINTENANCE WHERE Vehicle_ID = 5'
            ),
            1,
        )

        # A rented car is not offered in the form, so the post saves nothing.
        response = self.client.post(
            '/fleet/maintenance/new',
            data={
                'vehicle_id': '2',
                'start_date': date.today().isoformat(),
                'end_date': '',
                'description': 'Maintenance while rented',
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.count(
                'SELECT COUNT(*) AS total FROM MAINTENANCE WHERE Vehicle_ID = 2'
            ),
            0,
        )

        # Starting a job on a rented car is refused as well.
        job_id = execute(
            DB_CONFIG,
            """INSERT INTO MAINTENANCE (Vehicle_ID, Status, Start_Date)
               VALUES (2, 'scheduled', CURDATE())""",
        )
        response = self.client.post(
            f'/fleet/maintenance/{job_id}/start', follow_redirects=True
        )
        self.assertIn(
            'cannot start while the vehicle is rented',
            response.get_data(as_text=True),
        )
        self.assertEqual(
            fetchone(
                DB_CONFIG,
                'SELECT Status FROM MAINTENANCE WHERE Maintenance_ID = %s',
                (job_id,),
            )['Status'],
            'scheduled',
        )

        # A completed job no longer blocks the car.
        scheduled_job = execute(
            DB_CONFIG,
            """INSERT INTO MAINTENANCE (Vehicle_ID, Status, Start_Date)
               VALUES (3, 'scheduled', CURDATE())""",
        )
        self.assertTrue(self.rule(has_active_maintenance, 3))
        execute(
            DB_CONFIG,
            """UPDATE MAINTENANCE SET Status = 'completed', End_Date = CURDATE()
               WHERE Maintenance_ID = %s""",
            (scheduled_job,),
        )
        self.assertFalse(self.rule(has_active_maintenance, 3))

    # R5 ------------------------------------------------------------------

    def test_r5_driver_can_only_have_one_active_rental(self):
        self.assertFalse(self.rule(is_driver_free, 1), 'driver 1 is on rental 2')
        self.assertTrue(self.rule(is_driver_free, 2))

        self.add_open_rental(3, 2)
        self.assertFalse(self.rule(is_driver_free, 2))

        self.login('agent@example.com')
        response = self.client.post(
            '/agent/rentals/2/assign-driver',
            data={'driver_id': '2'},
            follow_redirects=True,
        )
        self.assertIn('Driver is not available', response.get_data(as_text=True))
        self.assertEqual(
            fetchone(
                DB_CONFIG, 'SELECT Driver_ID FROM RENTAL WHERE Rental_ID = 2'
            )['Driver_ID'],
            1,
        )

        # Closing the rental frees the driver again.
        execute(DB_CONFIG, 'UPDATE RENTAL SET Return_Date = CURDATE() WHERE Rental_ID = 2')
        self.assertTrue(self.rule(is_driver_free, 1))

    # R6 ------------------------------------------------------------------

    def test_r6_late_fee_is_days_late_times_rate_times_1_5(self):
        today = self.db_today()
        rental = fetchone(
            DB_CONFIG,
            """SELECT r.Due_Date, v.Daily_Rate
               FROM RENTAL r JOIN VEHICLE v ON v.Vehicle_ID = r.Vehicle_ID
               WHERE r.Rental_ID = 2""",
        )
        self.assertEqual(rental['Daily_Rate'], Decimal('4500.00'))
        self.assertEqual((today - rental['Due_Date']).days, 2)
        self.assertEqual(
            late_fee(rental['Daily_Rate'], rental['Due_Date'], today),
            Decimal('13500.00'),
        )

        # The README worked example: 3,500 per day, two days late.
        self.assertEqual(
            late_fee(Decimal('3500.00'), date(2026, 1, 10), date(2026, 1, 12)),
            Decimal('10500.00'),
        )

    # R7 ------------------------------------------------------------------

    def test_r7_tier_follows_completed_rentals(self):
        tier_sql = 'SELECT Tier FROM CUSTOMER WHERE Customer_ID = 1'
        # Amina already has one completed rental from the seed data.
        self.assertEqual(fetchone(DB_CONFIG, tier_sql)['Tier'], 'standard')

        for _ in range(3):
            self.add_returned_rental(1)
        self.assertEqual(fetchone(DB_CONFIG, tier_sql)['Tier'], 'standard')

        self.add_returned_rental(1)  # 5th completed rental
        self.assertEqual(fetchone(DB_CONFIG, tier_sql)['Tier'], 'silver')

        for _ in range(4):
            self.add_returned_rental(1)  # 9th
        self.assertEqual(fetchone(DB_CONFIG, tier_sql)['Tier'], 'silver')

        self.add_returned_rental(1)  # 10th
        self.assertEqual(fetchone(DB_CONFIG, tier_sql)['Tier'], 'gold')

    # R8 ------------------------------------------------------------------

    def test_r8_discount_never_applies_to_the_late_fee(self):
        # Carol's seed rental: 4,000 per day, two days late, no tier discount.
        rental = fetchone(
            DB_CONFIG,
            """SELECT r.Late_Fee, v.Daily_Rate
               FROM RENTAL r JOIN VEHICLE v ON v.Vehicle_ID = r.Vehicle_ID
               WHERE r.Rental_ID = 3""",
        )
        self.assertEqual(rental['Daily_Rate'], Decimal('4000.00'))
        self.assertEqual(rental['Late_Fee'], Decimal('12000.00'))

        execute(DB_CONFIG, "UPDATE CUSTOMER SET Tier = 'silver' WHERE Customer_ID = 3")
        stored = fetchone(
            DB_CONFIG, 'SELECT Late_Fee FROM RENTAL WHERE Rental_ID = 3'
        )['Late_Fee']
        self.assertEqual(stored, Decimal('12000.00'))

        fee = late_fee(Decimal('4000.00'), date(2026, 1, 10), date(2026, 1, 12))
        self.assertEqual(fee, Decimal('12000.00'))
        self.assertEqual(
            total_cost(Decimal('4000.00'), 2, 'silver'), Decimal('7600.00')
        )
        # The discount touches the rental cost, so it must be smaller than the fee.
        self.assertLess(
            total_cost(Decimal('4000.00'), 2, 'silver'),
            late_fee(Decimal('4000.00'), date(2026, 1, 10), date(2026, 1, 12)),
        )

    # R9 ------------------------------------------------------------------

    def test_r9_deleting_a_vehicle_keeps_its_rental_history(self):
        before = fetchone(
            DB_CONFIG,
            'SELECT Vehicle_ID, Late_Fee FROM RENTAL WHERE Rental_ID = 3',
        )
        self.assertEqual(before['Vehicle_ID'], 3)

        execute(DB_CONFIG, 'DELETE FROM INSURANCE_POLICY WHERE Vehicle_ID = 3')
        execute(DB_CONFIG, 'DELETE FROM VEHICLE WHERE Vehicle_ID = 3')

        after = fetchone(
            DB_CONFIG,
            'SELECT Vehicle_ID, Late_Fee FROM RENTAL WHERE Rental_ID = 3',
        )
        self.assertIsNotNone(after, 'the rental row must survive')
        self.assertIsNone(after['Vehicle_ID'])
        self.assertEqual(after['Late_Fee'], before['Late_Fee'])
        self.assertIsNone(
            fetchone(DB_CONFIG, 'SELECT 1 AS x FROM VEHICLE WHERE Vehicle_ID = 3')
        )

    # R10 -----------------------------------------------------------------

    def test_r10_reassign_checks_rules_and_logs_the_change(self):
        self.set_insurance_expired(1)
        self.add_open_rental(3, 2)  # driver 2 is busy from now on

        self.login('manager@example.com')
        history_count = 'SELECT COUNT(*) AS total FROM ASSIGNMENT_HISTORY'

        # Uninsured car: blocked and nothing logged.
        response = self.client.post(
            '/fleet/rentals/2/reassign',
            data={'vehicle_id': '1', 'driver_id': '1', 'reason': 'uninsured swap'},
            follow_redirects=True,
        )
        self.assertIn('Vehicle not available', response.get_data(as_text=True))
        self.assertEqual(self.count(history_count), 0)
        self.assertEqual(
            fetchone(
                DB_CONFIG, 'SELECT Vehicle_ID FROM RENTAL WHERE Rental_ID = 2'
            )['Vehicle_ID'],
            2,
        )

        # Driver already on an open rental: blocked and nothing logged.
        response = self.client.post(
            '/fleet/rentals/2/reassign',
            data={'vehicle_id': '2', 'driver_id': '2', 'reason': 'busy driver'},
            follow_redirects=True,
        )
        self.assertIn('Driver not available', response.get_data(as_text=True))
        self.assertEqual(self.count(history_count), 0)

        # Valid car and free driver: saved with exactly one history row.
        response = self.client.post(
            '/fleet/rentals/2/reassign',
            data={'vehicle_id': '4', 'driver_id': '3', 'reason': 'rule test'},
            follow_redirects=True,
        )
        self.assertIn('Change saved.', response.get_data(as_text=True))

        history = fetchall(
            DB_CONFIG,
            """SELECT Rental_ID, Old_Vehicle_ID, New_Vehicle_ID,
                      Old_Driver_ID, New_Driver_ID, Reason, Changed_By
               FROM ASSIGNMENT_HISTORY""",
        )
        self.assertEqual(len(history), 1)
        self.assertEqual(
            (
                history[0]['Rental_ID'],
                history[0]['Old_Vehicle_ID'],
                history[0]['New_Vehicle_ID'],
                history[0]['Old_Driver_ID'],
                history[0]['New_Driver_ID'],
                history[0]['Reason'],
            ),
            (2, 2, 4, 1, 3, 'rule test'),
        )
        self.assertEqual(
            history[0]['Changed_By'],
            fetchone(
                DB_CONFIG,
                'SELECT User_ID FROM USER_ACCOUNT WHERE Email = %s',
                ('manager@example.com',),
            )['User_ID'],
        )
        self.assertEqual(
            fetchone(
                DB_CONFIG, 'SELECT Status FROM VEHICLE WHERE Vehicle_ID = 4'
            )['Status'],
            'rented',
        )
        self.assertEqual(
            fetchone(
                DB_CONFIG, 'SELECT Status FROM DRIVER WHERE Driver_ID = 3'
            )['Status'],
            'assigned',
        )


if __name__ == '__main__':
    unittest.main()
