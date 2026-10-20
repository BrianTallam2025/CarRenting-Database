import os
from decimal import Decimal

from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY', 'dev-only-change-me')
DB_CONFIG = dict(
    host=os.getenv('DB_HOST', '127.0.0.1'),
    port=int(os.getenv('DB_PORT', 3306)),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'),
)

LATE_FEE_MULTIPLIER = Decimal('1.5')
TIER_DISCOUNTS = {
    'standard': Decimal('0'),
    'silver': Decimal('0.05'),
    'gold': Decimal('0.10'),
}
