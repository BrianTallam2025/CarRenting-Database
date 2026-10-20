from decimal import Decimal, ROUND_HALF_UP

from app.config import LATE_FEE_MULTIPLIER, TIER_DISCOUNTS


def money(value):
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def rental_days(start_date, end_date):
    return max(1, (end_date - start_date).days)


def total_cost(daily_rate, days, tier):
    discount = TIER_DISCOUNTS[tier]
    return money(Decimal(daily_rate) * days * (1 - discount))


def late_fee(daily_rate, due_date, return_date):
    days_late = max(0, (return_date - due_date).days)
    return money(Decimal(daily_rate) * days_late * LATE_FEE_MULTIPLIER)
