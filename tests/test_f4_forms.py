"""F4 form tests: field-level errors and submitted values stay on the page.

The fleet routes re-render their form when validation fails, so the page
must show the message next to the field and keep what the user typed.
"""

import os
import re
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

TEST_DB = 'car_rental_f4_test'
os.environ['DB_NAME'] = TEST_DB

from app import create_app  # noqa: E402
from app.config import DB_CONFIG  # noqa: E402
from db_support import create_accounts, drop_database, reset_database  # noqa: E402

ACCOUNTS = [('manager@example.com', 'fleet_manager', None, None)]


class FleetFormTests(unittest.TestCase):
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
        response = self.client.post(
            '/login',
            data={'email': 'manager@example.com', 'password': 'demo1234'},
        )
        self.assertEqual(response.status_code, 302)

    @classmethod
    def tearDownClass(cls):
        drop_database(DB_CONFIG, TEST_DB)

    def post(self, path, data):
        response = self.client.post(path, data=data)
        self.assertEqual(response.status_code, 200, path)
        return response.get_data(as_text=True)

    def test_new_vehicle_keeps_values_and_shows_field_error(self):
        body = self.post('/fleet/vehicles/new', {
            'vin': 'TESTVIN000000001',
            'plate_number': 'TST 001X',
            'make': '',
            'model': 'Corolla',
            'year': '2024',
            'daily_rate': '3500',
        })

        self.assertIn('This field is required.', body)
        self.assertIn('value="TESTVIN000000001"', body)
        self.assertIn('value="TST 001X"', body)
        self.assertIn('value="Corolla"', body)
        # The message sits next to the make field, not only in the flash area.
        self.assertRegex(body, r'id="make"[^>]*>[\s\S]{0,400}?form-error')
        self.assertNotIn('Vehicle added.', body)

    def test_new_driver_duplicate_licence_keeps_values(self):
        body = self.post('/fleet/drivers/new', {
            'first_name': 'Copy',
            'last_name': 'Driver',
            'license_number': 'DL-2017-003344',
        })

        self.assertIn('already registered', body)
        self.assertIn('value="Copy"', body)
        self.assertIn('value="DL-2017-003344"', body)

    def test_maintenance_form_keeps_the_chosen_car(self):
        body = self.post('/fleet/maintenance/new', {
            'vehicle_id': '5',
            'start_date': date.today().isoformat(),
            'end_date': '',
            'description': '',
        })

        self.assertIn('This field is required.', body)
        option = re.search(r'<option[^>]*value="5"[^>]*>', body)
        self.assertIsNotNone(option, 'the chosen car must stay selected')
        self.assertIn('selected', option.group(0))

    def test_insurance_form_shows_missing_car(self):
        body = self.post('/fleet/insurance', {
            'vehicle_id': '0',
            'provider': 'Jubilee',
            'expiry_date': '2027-01-01',
        })

        self.assertIn('This field is required.', body)
        self.assertIn('value="Jubilee"', body)


if __name__ == '__main__':
    unittest.main()
