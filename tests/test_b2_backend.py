import unittest
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from app import create_app
from app.services.pricing import late_fee, total_cost
from app.services.rules import has_active_maintenance


class PricingTests(unittest.TestCase):
    def test_two_days_late_at_3500_per_day_costs_10500(self):
        self.assertEqual(
            late_fee(
                Decimal('3500.00'),
                date(2026, 1, 10),
                date(2026, 1, 12),
            ),
            Decimal('10500.00'),
        )

    def test_on_time_return_has_no_late_fee(self):
        self.assertEqual(
            late_fee(
                Decimal('3500.00'),
                date(2026, 1, 10),
                date(2026, 1, 10),
            ),
            Decimal('0.00'),
        )

    def test_late_fee_does_not_apply_customer_discount(self):
        self.assertEqual(
            late_fee(
                Decimal('3500.00'),
                date(2026, 1, 10),
                date(2026, 1, 12),
            ),
            Decimal('10500.00'),
        )
        self.assertEqual(
            total_cost(Decimal('3500.00'), 3, 'silver'),
            Decimal('9975.00'),
        )


class MaintenanceRuleTests(unittest.TestCase):
    @patch('app.services.rules.query', return_value={'1': 1})
    def test_scheduled_maintenance_counts_as_active(self, query_mock):
        self.assertTrue(has_active_maintenance(7))
        self.assertIn("Status IN ('scheduled', 'in_progress')", query_mock.call_args.args[0])

    @patch('app.services.rules.query', return_value=None)
    def test_vehicle_without_active_maintenance_is_clear(self, query_mock):
        self.assertFalse(has_active_maintenance(7))


class RouteRegistrationTests(unittest.TestCase):
    def test_b2_pages_and_maintenance_actions_are_registered(self):
        app = create_app()
        routes = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertTrue(
            {
                '/my-rentals',
                '/agent',
                '/agent/rentals',
                '/agent/rentals/<int:rental_id>',
                '/agent/rentals/<int:rental_id>/return',
                '/agent/customers',
                '/fleet',
                '/fleet/vehicles',
                '/fleet/insurance',
                '/fleet/maintenance',
                '/fleet/drivers',
                '/fleet/maintenance/<int:maintenance_id>/start',
                '/fleet/maintenance/<int:maintenance_id>/complete',
            }.issubset(routes)
        )


class B2PageContractTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                'TESTING': True,
                'WTF_CSRF_ENABLED': False,
                'SECRET_KEY': 'test-secret',
            }
        )
        self.client = self.app.test_client()

    @contextmanager
    def login(self, role):
        user = {
            'User_ID': 1,
            'Email': 'test@example.com',
            'Role': role,
            'Customer_ID': 1 if role == 'customer' else None,
            'Driver_ID': None,
        }
        with patch('app.auth.query', return_value=user):
            with self.client.session_transaction() as session:
                session['_user_id'] = '1'
                session['_fresh'] = True
            yield

    def test_return_page_renders_late_fee_preview_and_amount_due(self):
        rental = {
            'Rental_ID': 7,
            'Rental_Date': date.today() - timedelta(days=3),
            'Due_Date': date.today() - timedelta(days=2),
            'Return_Date': None,
            'Total_Cost': Decimal('9975.00'),
            'Late_Fee': Decimal('0.00'),
            'Daily_Rate': Decimal('3500.00'),
            'Vehicle_ID': 1,
            'Driver_ID': None,
            'Customer_First_Name': 'Amina',
            'Customer_Last_Name': 'Wanjiru',
            'Customer_Email': 'amina@example.com',
            'Customer_Tier': 'silver',
            'Make': 'Toyota',
            'Model': 'Corolla',
            'Plate_Number': 'KDA 101A',
            'Driver_First_Name': None,
            'Driver_Last_Name': None,
            'Is_Chauffeur': False,
        }
        with self.login('rental_agent'):
            with patch('app.blueprints.returns.query', return_value=rental):
                response = self.client.get('/agent/rentals/7/return')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Amina Wanjiru', response.data)
        self.assertIn(b'KES 3500.00/day', response.data)
        self.assertIn(b'KES 10500.00', response.data)
        self.assertIn(b'KES 20475.00', response.data)
        self.assertIn(b'name="return_date"', response.data)

    def test_agent_dashboard_uses_contract_context_names(self):
        counts = {'active': 2, 'due_today': 1, 'overdue': 1, 'available': 3}
        due_today = [{'Rental_ID': 1}]
        overdue = [{'Rental_ID': 2, 'days_late': 2}]
        with self.login('rental_agent'):
            with patch(
                'app.blueprints.returns.query',
                side_effect=[counts, due_today, overdue],
            ):
                with patch(
                    'app.blueprints.returns.render_template',
                    return_value='dashboard',
                ) as render:
                    response = self.client.get('/agent')

        self.assertEqual(response.status_code, 200)
        context = render.call_args.kwargs
        self.assertEqual(context['counts'], counts)
        self.assertEqual(context['due_today'], due_today)
        self.assertEqual(context['overdue'], overdue)
        self.assertNotIn('summary', context)

    def test_customer_lookup_includes_selected_customer_rentals(self):
        customers = [{'Customer_ID': 1, 'First_Name': 'Amina'}]
        selected = {
            'Customer_ID': 1,
            'First_Name': 'Amina',
            'Last_Name': 'Wanjiru',
            'Tier': 'silver',
        }
        rentals = [{'Rental_ID': 9, 'Make': 'Toyota', 'Model': 'Corolla'}]
        with self.login('rental_agent'):
            with patch(
                'app.blueprints.returns.query',
                side_effect=[customers, selected, rentals],
            ) as query_mock:
                with patch(
                    'app.blueprints.returns.render_template',
                    return_value='customers',
                ) as render:
                    response = self.client.get('/agent/customers?q=Amina&selected=1')

        self.assertEqual(response.status_code, 200)
        self.assertIn('License_Number', query_mock.call_args_list[0].args[0])
        context = render.call_args.kwargs
        self.assertEqual(context['customers'], customers)
        self.assertEqual(context['selected'], selected)
        self.assertEqual(context['rentals'], rentals)


if __name__ == '__main__':
    unittest.main()
