import unittest
from datetime import date
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


if __name__ == '__main__':
    unittest.main()
