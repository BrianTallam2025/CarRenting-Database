# Car Rental System

Group project for **CNS_DES**. A database-backed website for a car rental company, built with **Flask, MySQL, plain HTML and CSS**. Customers rent cars (self-drive or with a chauffeur), staff run the desk and the fleet, and drivers see their own assignments.

This README is the single source of truth for the team. If something here and something in your head disagree, this file wins, and if it's wrong, fix it in a pull request.

## Table of contents

1. [Overview](#1-overview)
2. [Roles and permissions (RBAC)](#2-roles-and-permissions-rbac)
3. [Tech stack](#3-tech-stack)
4. [How a request flows](#4-how-a-request-flows)
5. [Project structure](#5-project-structure)
6. [Getting started](#6-getting-started)
7. [Database](#7-database)
8. [Business rules, pricing and status changes](#8-business-rules-pricing-and-status-changes)
9. [Backend conventions with code](#9-backend-conventions-with-code)
10. [All 32 pages and routes](#10-all-32-pages-and-routes)
11. [API_CONTRACT.md](#11-api_contractmd)
12. [Frontend guide](#12-frontend-guide)
13. [Team and ownership](#13-team-and-ownership)
14. [Git workflow](#14-git-workflow)
15. [Timeline](#15-timeline)
16. [Testing](#16-testing)
17. [Security checklist](#17-security-checklist)
18. [Troubleshooting](#18-troubleshooting)
19. [Out of scope and future ideas](#19-out-of-scope-and-future-ideas)
20. [Glossary](#20-glossary)

---

## 1. Overview

**What it does:** customers browse available cars, rent one for a number of days (with or without a driver), and track their rentals. Rental agents handle walk-ins, assign drivers and process returns. Fleet managers look after the cars, insurance, maintenance and drivers. Drivers log in to see the car they were assigned.

**What makes it different from a basic rental site:**

| Feature | What it means |
|---|---|
| Self-drive or chauffeur | A rental can include a driver from the driver pool |
| Insurance tracking | A car whose insurance has expired cannot be rented |
| Loyalty tiers | Standard, Silver and Gold, based on completed rentals, with a discount |
| RBAC | Four roles, each with its own pages, enforced on the server |
| Audit trail | Every change of car or driver on a rental is logged |

---

## 2. Roles and permissions (RBAC)

| Role | Who | Can do |
|---|---|---|
| `customer` | Someone renting a car | Browse cars, rent, see own rentals, tier and profile |
| `rental_agent` | Desk staff | Walk-in rentals, process returns, assign drivers, view all rentals, look up customers |
| `fleet_manager` | The owner of the cars | Everything about the fleet (cars, insurance, maintenance, driver list), and change the car or driver on a rental |
| `driver` | A chauffeur | See only their own current assignment, upcoming jobs and past trips |

**How it's enforced:** every route is wrapped in `@role_required(...)`. The server checks the logged-in user's role, and a wrong role gets a `403` page. Hiding a menu link is only for looks, never for security.

**Data isolation rules:**
- A driver's pages filter by the logged-in driver's own `Driver_ID`, never an ID from the URL.
- A customer's pages filter by the logged-in customer's own `Customer_ID`.
- A driver sees only the customer's name and phone for their active job, never other customer data.

---

## 3. Tech stack

| Tool | Used for |
|---|---|
| Python 3.10+ and Flask | Backend: routes, rules, sessions |
| Jinja2 (comes with Flask) | HTML templates with gaps the backend fills |
| HTML and CSS | Page structure and styling (we write our own CSS, no Bootstrap or Tailwind) |
| JavaScript (small) | Live price preview on the rent form, confirm pop-ups |
| MySQL 8.0.16 or newer | Database. Older versions ignore `CHECK` constraints |
| PyMySQL (+ `cryptography`) | Lets Flask talk to MySQL. `cryptography` is needed for MySQL 8 logins |
| Flask-Login | Keeps users logged in between pages |
| Flask-WTF | Forms and CSRF protection |
| Werkzeug | Password hashing (installed with Flask) |
| python-dotenv | Reads secrets from a `.env` file |
| Git and GitHub | Version control, one branch per feature |

**Deliberately not used:** an ORM such as SQLAlchemy. Our business rules are written as SQL in the report, and raw SQL keeps the code and the report identical.

`requirements.txt`:

```
Flask
Flask-Login
Flask-WTF
PyMySQL
cryptography
python-dotenv
```

---

## 4. How a request flows

```
Browser  ->  Flask route  ->  MySQL
   ^              |
   |              v
   +-----  Jinja template (HTML with gaps)
```

Example: a customer opens **Browse cars**.

1. The browser requests `/vehicles`.
2. The route function asks MySQL for cars that are available and insured.
3. Flask passes the list to `customer/vehicles.html`.
4. The template fills in the gaps and the finished HTML goes back to the browser.

For a form (such as renting), the browser sends a `POST`, the route validates it, checks the business rules, writes to MySQL, then redirects to a confirmation page.

---

## 5. Project structure

```
car-rental/
├── app/
│   ├── __init__.py            # create_app(): config, login manager, CSRF, blueprints   (B1)
│   ├── config.py              # constants: late fee multiplier, tier discounts          (B1)
│   ├── db.py                  # connection helpers: query(), execute(), get_db()        (B1)
│   ├── auth.py                # User class, login manager, role_required                (B1)
│   ├── forms.py               # Flask-WTF forms (RentForm, ReturnForm, ...)             (B1)
│   ├── services/
│   │   ├── rules.py           # shared rule checks (availability, driver free, etc.)
│   │   └── pricing.py         # total cost and late fee calculations
│   ├── blueprints/            # backend routes, one file per area
│   │   ├── main.py            # landing, errors                                          (B1)
│   │   ├── accounts.py        # register, login, logout, customer dashboard, profile    (B1)
│   │   ├── rent.py            # browse, details, rent, confirmation, walk-in             (B1)
│   │   ├── assignments.py     # assign driver, reassign, history, driver portal          (B1)
│   │   ├── returns.py         # process return, rental lists and details                 (B2)
│   │   └── fleet.py           # vehicles, insurance, maintenance, driver pool            (B2)
│   ├── templates/             # frontend pages
│   │   ├── shared/            # base.html, landing, login, register, 403, error         (F1)
│   │   ├── driver/            # current assignment, trip history                          (F1)
│   │   ├── customer/          # dashboard, browse, details, rent, my rentals...           (F2)
│   │   ├── agent/             # agent dashboard, rentals, return, assign...               (F3)
│   │   └── fleet/             # fleet pages, plus reassign and history pages (F3)         (F4)
│   └── static/
│       ├── css/main.css       # shared styles                                             (F1)
│       ├── css/components/    # each person's own component CSS files
│       └── js/                # small scripts (price preview, confirm dialogs)
├── schema.sql                 # all tables, trigger                                       (B2)
├── seed.sql                   # sample cars, customers, drivers                           (B2)
├── seed_users.py              # creates login accounts with hashed passwords              (B2)
├── tests/                     # SQL test scripts, one per business rule                   (B2)
├── API_CONTRACT.md            # every page: route, roles, variables, form fields          (B1)
├── requirements.txt
├── .env.example
├── .gitignore
├── run.py
└── README.md
```

Each person works in their own folders, so two people almost never edit the same file. The shared files are `base.html` and `main.css` (F1 only), and `db.py`, `auth.py`, `config.py` (B1 only).

`.gitignore`:

```
venv/
.env
__pycache__/
*.pyc
instance/
```

---

## 6. Getting started

**Prerequisites:** Python 3.10+, MySQL 8.0.16+, Git.

Each person runs **their own local MySQL** and loads the schema and seed data, so nobody breaks anyone else's data.

```bash
# 1. Get the code
git clone <repo-url>
cd car-rental

# 2. Private Python environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure secrets
cp .env.example .env              # then edit .env (see below)

# 5. Create the database
mysql -u root -p < schema.sql
mysql -u root -p car_rental < seed.sql

# 6. Create login accounts (hashed passwords)
python seed_users.py

# 7. Run
flask --app run run --debug
```

Open <http://127.0.0.1:5000>.

**`.env.example`:**

```
SECRET_KEY=change-me-to-a-long-random-string
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=rental_dev
DB_PASSWORD=your_password
DB_NAME=car_rental
```

**Create the MySQL user** (inside the `mysql` shell):

```sql
CREATE USER 'rental_dev'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON car_rental.* TO 'rental_dev'@'localhost';
FLUSH PRIVILEGES;
```

**MySQL running in WSL2 and Workbench on Windows:** set `bind-address = 0.0.0.0` in `/etc/mysql/mysql.conf.d/mysqld.cnf`, restart with `sudo service mysql restart`, and create the user with host `'%'` instead of `'localhost'`. Connect Workbench to `127.0.0.1:3306`, or to the WSL2 IP from `ip addr show eth0`.

**Demo accounts** created by `seed_users.py` (change these before any real use):

| Email | Role | Password |
|---|---|---|
| customer@demo.test | customer | `demo1234` |
| agent@demo.test | rental_agent | `demo1234` |
| manager@demo.test | fleet_manager | `demo1234` |
| driver@demo.test | driver | `demo1234` |

`seed_users.py`:

```python
import os
import pymysql
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()
db = pymysql.connect(
    host=os.getenv('DB_HOST'), port=int(os.getenv('DB_PORT', 3306)),
    user=os.getenv('DB_USER'), password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'),
)
pw = generate_password_hash('demo1234')
accounts = [
    ('customer@demo.test', 'customer', 1, None),
    ('agent@demo.test', 'rental_agent', None, None),
    ('manager@demo.test', 'fleet_manager', None, None),
    ('driver@demo.test', 'driver', None, 1),
]
with db.cursor() as cur:
    for email, role, cust, drv in accounts:
        cur.execute(
            'INSERT IGNORE INTO USER_ACCOUNT (Email, Password_Hash, Role, Customer_ID, Driver_ID) '
            'VALUES (%s, %s, %s, %s, %s)', (email, pw, role, cust, drv))
db.commit()
print('Accounts created.')
```

---

## 7. Database

Nine tables. The full script lives in `schema.sql` (B2 owns it, and it is frozen on day 0).

| Table | Stores |
|---|---|
| `VEHICLE` | Each car: VIN, plate, make, model, year, daily rate, status |
| `INSURANCE_POLICY` | One policy per car, with expiry date |
| `CUSTOMER` | Customer details, license number and expiry, loyalty tier |
| `CUSTOMER_PHONE` | Several phone numbers per customer (keeps the tables in 1NF) |
| `DRIVER` | Chauffeurs, status `available` or `assigned` |
| `USER_ACCOUNT` | Logins: email, password hash, role, link to customer or driver |
| `RENTAL` | Every rental: customer, car, optional driver, dates, total cost, late fee |
| `MAINTENANCE` | Service jobs per car |
| `ASSIGNMENT_HISTORY` | Log of every car or driver change on a rental |

### Relationships

- One customer has many phone numbers and many rentals.
- One car has one insurance policy, many rentals and many maintenance jobs.
- One rental belongs to one customer, one car and optionally one driver.
- A `USER_ACCOUNT` links to at most one customer or one driver. Agents and managers link to neither.

### schema.sql

```sql
CREATE DATABASE IF NOT EXISTS car_rental;
USE car_rental;

CREATE TABLE VEHICLE (
    Vehicle_ID    INT PRIMARY KEY AUTO_INCREMENT,
    VIN           VARCHAR(17) UNIQUE NOT NULL,
    Plate_Number  VARCHAR(15) UNIQUE NOT NULL,
    Make          VARCHAR(50) NOT NULL,
    Model         VARCHAR(50) NOT NULL,
    Year          INT NOT NULL,
    Daily_Rate    DECIMAL(10,2) NOT NULL,
    Status        VARCHAR(20) NOT NULL DEFAULT 'available'
                  CHECK (Status IN ('available', 'rented', 'maintenance'))
);

CREATE TABLE INSURANCE_POLICY (
    Policy_ID    INT PRIMARY KEY AUTO_INCREMENT,
    Vehicle_ID   INT NOT NULL UNIQUE,
    Provider     VARCHAR(100) NOT NULL,
    Expiry_Date  DATE NOT NULL,
    FOREIGN KEY (Vehicle_ID) REFERENCES VEHICLE(Vehicle_ID)
);

CREATE TABLE CUSTOMER (
    Customer_ID     INT PRIMARY KEY AUTO_INCREMENT,
    National_ID     VARCHAR(20) UNIQUE NOT NULL,
    First_Name      VARCHAR(50) NOT NULL,
    Last_Name       VARCHAR(50) NOT NULL,
    Email           VARCHAR(100) UNIQUE NOT NULL,
    License_Number  VARCHAR(30) UNIQUE NOT NULL,
    License_Expiry  DATE NOT NULL,
    Tier            VARCHAR(20) NOT NULL DEFAULT 'standard'
                    CHECK (Tier IN ('standard', 'silver', 'gold'))
);

CREATE TABLE CUSTOMER_PHONE (
    Customer_ID   INT,
    Phone_Number  VARCHAR(20),
    PRIMARY KEY (Customer_ID, Phone_Number),
    FOREIGN KEY (Customer_ID) REFERENCES CUSTOMER(Customer_ID) ON DELETE CASCADE
);

CREATE TABLE DRIVER (
    Driver_ID       INT PRIMARY KEY AUTO_INCREMENT,
    First_Name      VARCHAR(50) NOT NULL,
    Last_Name       VARCHAR(50) NOT NULL,
    License_Number  VARCHAR(30) UNIQUE NOT NULL,
    Status          VARCHAR(20) NOT NULL DEFAULT 'available'
                    CHECK (Status IN ('available', 'assigned'))
);

CREATE TABLE USER_ACCOUNT (
    User_ID        INT PRIMARY KEY AUTO_INCREMENT,
    Email          VARCHAR(100) UNIQUE NOT NULL,
    Password_Hash  VARCHAR(255) NOT NULL,
    Role           VARCHAR(20) NOT NULL
                   CHECK (Role IN ('customer', 'rental_agent', 'fleet_manager', 'driver')),
    Customer_ID    INT UNIQUE,
    Driver_ID      INT UNIQUE,
    FOREIGN KEY (Customer_ID) REFERENCES CUSTOMER(Customer_ID) ON DELETE CASCADE,
    FOREIGN KEY (Driver_ID)   REFERENCES DRIVER(Driver_ID)     ON DELETE CASCADE
);

CREATE TABLE RENTAL (
    Rental_ID     INT PRIMARY KEY AUTO_INCREMENT,
    Customer_ID   INT NOT NULL,
    Vehicle_ID    INT,
    Driver_ID     INT,
    Is_Chauffeur  BOOLEAN NOT NULL DEFAULT FALSE,
    Rental_Date   DATE NOT NULL,
    Due_Date      DATE NOT NULL,
    Return_Date   DATE,
    Total_Cost    DECIMAL(10,2) NOT NULL,
    Late_Fee      DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    FOREIGN KEY (Customer_ID) REFERENCES CUSTOMER(Customer_ID),
    FOREIGN KEY (Vehicle_ID)  REFERENCES VEHICLE(Vehicle_ID) ON DELETE SET NULL,
    FOREIGN KEY (Driver_ID)   REFERENCES DRIVER(Driver_ID)   ON DELETE SET NULL
);

CREATE TABLE MAINTENANCE (
    Maintenance_ID  INT PRIMARY KEY AUTO_INCREMENT,
    Vehicle_ID      INT NOT NULL,
    Status          VARCHAR(20) NOT NULL DEFAULT 'scheduled'
                    CHECK (Status IN ('scheduled', 'in_progress', 'completed')),
    Start_Date      DATE NOT NULL,
    End_Date        DATE,
    Description     VARCHAR(255),
    FOREIGN KEY (Vehicle_ID) REFERENCES VEHICLE(Vehicle_ID)
);

CREATE TABLE ASSIGNMENT_HISTORY (
    History_ID      INT PRIMARY KEY AUTO_INCREMENT,
    Rental_ID       INT NOT NULL,
    Old_Vehicle_ID  INT,
    New_Vehicle_ID  INT,
    Old_Driver_ID   INT,
    New_Driver_ID   INT,
    Changed_By      INT NOT NULL,
    Changed_At      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Reason          VARCHAR(255),
    FOREIGN KEY (Rental_ID)      REFERENCES RENTAL(Rental_ID),
    FOREIGN KEY (Old_Vehicle_ID) REFERENCES VEHICLE(Vehicle_ID) ON DELETE SET NULL,
    FOREIGN KEY (New_Vehicle_ID) REFERENCES VEHICLE(Vehicle_ID) ON DELETE SET NULL,
    FOREIGN KEY (Old_Driver_ID)  REFERENCES DRIVER(Driver_ID)   ON DELETE SET NULL,
    FOREIGN KEY (New_Driver_ID)  REFERENCES DRIVER(Driver_ID)   ON DELETE SET NULL,
    FOREIGN KEY (Changed_By)     REFERENCES USER_ACCOUNT(User_ID)
);
```

### Loyalty tier trigger

Runs by itself the moment a rental gets its `Return_Date`, and recalculates the customer's tier from their completed rentals.

```sql
DELIMITER $$
CREATE TRIGGER trg_update_tier AFTER UPDATE ON RENTAL
FOR EACH ROW
BEGIN
  IF OLD.Return_Date IS NULL AND NEW.Return_Date IS NOT NULL THEN
    UPDATE CUSTOMER SET Tier = CASE
      WHEN (SELECT COUNT(*) FROM RENTAL
            WHERE Customer_ID = NEW.Customer_ID AND Return_Date IS NOT NULL) >= 10 THEN 'gold'
      WHEN (SELECT COUNT(*) FROM RENTAL
            WHERE Customer_ID = NEW.Customer_ID AND Return_Date IS NOT NULL) >= 5 THEN 'silver'
      ELSE 'standard' END
    WHERE Customer_ID = NEW.Customer_ID;
  END IF;
END$$
DELIMITER ;
```

The thresholds (5 and 10) are written into the trigger. If the team changes them, change `config.py` and this trigger together.

### Rules that cannot be plain constraints

SQL `CHECK` cannot count other rows or look at other tables, so these three are enforced in Python (`services/rules.py`), inside the same database transaction as the write:

1. One active maintenance job per car.
2. One active rental per driver.
3. A car can only be rented when its status is `available` and its insurance has not expired.

---

## 8. Business rules, pricing and status changes

### The rules

| # | Rule | Enforced by |
|---|---|---|
| R1 | Every car has a unique VIN and plate | `UNIQUE` constraints |
| R2 | A customer needs an unexpired driving license to rent | `rules.customer_license_valid` |
| R3 | A car can be rented only if `available` and insured | `rules.is_vehicle_available` |
| R4 | One active maintenance job per car, and none while the car is rented | `rules.has_active_maintenance` and a status check |
| R5 | A driver can be on one active rental at a time | `rules.is_driver_free` |
| R6 | Late fee = days late x daily rate x 1.5 | `pricing.late_fee` |
| R7 | Tier from completed rentals: 0-4 Standard, 5-9 Silver (5%), 10+ Gold (10%) | Trigger `trg_update_tier` |
| R8 | The discount applies to rental cost only, never to the late fee | `pricing.total_cost` |
| R9 | Removing a car must not delete its rental history | `ON DELETE SET NULL` on `RENTAL.Vehicle_ID` |
| R10 | Changing car or driver on a rental passes R3 and R5 and is logged | `assignments.py` plus `ASSIGNMENT_HISTORY` |
| R11 | Age or similar derived values are computed, never stored | Design rule |

### Pricing

- **Total cost** = days x daily rate x (1 - discount). Saved in `RENTAL.Total_Cost` when the rental is created. Days is at least 1.
- **Late fee** is worked out on return and saved in `RENTAL.Late_Fee`.
- **Amount due** = `Total_Cost` + `Late_Fee`.

Worked example: a Corolla at KES 3,500 per day, 3 days, Silver customer.

| Step | Calculation | Result |
|---|---|---|
| Base | 3 x 3,500 | 10,500 |
| Discount (5%) | 10,500 x 0.05 | 525 |
| Total cost | 10,500 - 525 | **9,975** |
| Returned 2 days late | 2 x 3,500 x 1.5 | **10,500** |
| Amount due | 9,975 + 10,500 | **20,475** |

B1 writes `Total_Cost`. B2 writes `Late_Fee`. Neither edits the other's column.

### What changes when something happens

| Event | Done by | Car status | Driver status |
|---|---|---|---|
| Rental created | B1 | available -> rented | chauffeur only: available -> assigned |
| Car or driver changed | B1 | old car -> available (or maintenance), new car -> rented | old driver -> available, new driver -> assigned |
| Return processed | B2 | rented -> available | assigned -> available |
| Maintenance started | B2 | -> maintenance | none |
| Maintenance finished | B2 | -> available | none |

Scheduling maintenance on a car whose status is `rented` is rejected.

---

## 9. Backend conventions with code

### Where things live

- **Raw SQL** is written in blueprints through `query()` and `execute()` from `db.py`, always with `%s` placeholders. Never build SQL with f-strings.
- **Rule checks** live in `services/rules.py` so every route uses the same check.
- **Money maths** lives in `services/pricing.py`. Never calculate prices inside a route.
- **Constants** live in `config.py`.

### `app/config.py`

```python
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
```

### `app/db.py`

```python
import pymysql
from flask import g
from app.config import DB_CONFIG


def get_db():
    if 'db' not in g:
        g.db = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **DB_CONFIG)
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def query(sql, params=(), one=False):
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def execute(sql, params=()):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(sql, params)
        last_id = cur.lastrowid
    db.commit()
    return last_id
```

For changes that must succeed or fail together (for example create a rental and mark the car rented), use `get_db()` directly, run several statements, then call `db.commit()` once. On an error call `db.rollback()`.

### `app/auth.py`

```python
from functools import wraps
from flask import abort
from flask_login import LoginManager, UserMixin, current_user, login_required
from app.db import query

login_manager = LoginManager()
login_manager.login_view = 'accounts.login'


class User(UserMixin):
    def __init__(self, row):
        self.id = row['User_ID']
        self.email = row['Email']
        self.role = row['Role']
        self.customer_id = row['Customer_ID']
        self.driver_id = row['Driver_ID']


@login_manager.user_loader
def load_user(user_id):
    row = query('SELECT * FROM USER_ACCOUNT WHERE User_ID = %s', (user_id,), one=True)
    return User(row) if row else None


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator
```

### `app/services/rules.py`

```python
from app.db import query


def is_vehicle_available(vehicle_id):
    row = query(
        """SELECT 1 FROM VEHICLE v
           JOIN INSURANCE_POLICY i ON i.Vehicle_ID = v.Vehicle_ID
           WHERE v.Vehicle_ID = %s AND v.Status = 'available'
             AND i.Expiry_Date > CURDATE()""",
        (vehicle_id,), one=True)
    return row is not None


def is_driver_free(driver_id):
    row = query(
        'SELECT 1 FROM RENTAL WHERE Driver_ID = %s AND Return_Date IS NULL',
        (driver_id,), one=True)
    return row is None


def has_active_maintenance(vehicle_id):
    row = query(
        "SELECT 1 FROM MAINTENANCE WHERE Vehicle_ID = %s AND Status = 'in_progress'",
        (vehicle_id,), one=True)
    return row is not None


def customer_license_valid(customer_id):
    row = query(
        'SELECT 1 FROM CUSTOMER WHERE Customer_ID = %s AND License_Expiry > CURDATE()',
        (customer_id,), one=True)
    return row is not None
```

### `app/services/pricing.py`

```python
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
```

### The route pattern to copy

This is the shape every route follows: check the role, load data, validate the form, check the rules, write inside one transaction, redirect. B1 ships the Rent route first as the template for everyone else.

```python
from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import current_user
from app.auth import role_required
from app.db import query, get_db
from app.services import rules, pricing
from app.forms import RentForm

bp = Blueprint('rent', __name__)


@bp.route('/rent/<int:vehicle_id>', methods=['GET', 'POST'])
@role_required('customer')
def rent(vehicle_id):
    vehicle = query('SELECT * FROM VEHICLE WHERE Vehicle_ID = %s', (vehicle_id,), one=True)
    if vehicle is None:
        abort(404)
    customer = query('SELECT * FROM CUSTOMER WHERE Customer_ID = %s',
                     (current_user.customer_id,), one=True)

    form = RentForm()
    if form.validate_on_submit():
        if not rules.customer_license_valid(customer['Customer_ID']):
            flash('Your driving license has expired.', 'error')
        elif not rules.is_vehicle_available(vehicle_id):
            flash('Vehicle not available.', 'error')
        else:
            days = pricing.rental_days(form.start_date.data, form.end_date.data)
            cost = pricing.total_cost(vehicle['Daily_Rate'], days, customer['Tier'])
            db = get_db()
            try:
                with db.cursor() as cur:
                    cur.execute(
                        'INSERT INTO RENTAL (Customer_ID, Vehicle_ID, Is_Chauffeur, '
                        'Rental_Date, Due_Date, Total_Cost) VALUES (%s, %s, %s, %s, %s, %s)',
                        (customer['Customer_ID'], vehicle_id, form.is_chauffeur.data,
                         form.start_date.data, form.end_date.data, cost))
                    rental_id = cur.lastrowid
                    cur.execute("UPDATE VEHICLE SET Status = 'rented' WHERE Vehicle_ID = %s",
                                (vehicle_id,))
                db.commit()
            except Exception:
                db.rollback()
                raise
            return redirect(url_for('rent.confirmation', rental_id=rental_id))

    return render_template('customer/rent.html', vehicle=vehicle,
                           customer=customer, form=form)
```

### `app/__init__.py`

```python
from flask import Flask, render_template
from flask_wtf import CSRFProtect
from app import config
from app.auth import login_manager
from app.db import close_db

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = config.SECRET_KEY

    csrf.init_app(app)
    login_manager.init_app(app)
    app.teardown_appcontext(close_db)

    from app.blueprints import main, accounts, rent, assignments, returns, fleet
    for module in (main, accounts, rent, assignments, returns, fleet):
        app.register_blueprint(module.bp)

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('shared/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('shared/error.html', code=404), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('shared/error.html', code=500), 500

    return app
```

`run.py`:

```python
from app import create_app

app = create_app()
```

---

## 10. All 32 pages and routes

Routes are provisional until B1 confirms them in `API_CONTRACT.md`. "Backend" is who writes the route. "Frontend" is who writes the template.

### F1: shared, public and driver pages (7)

| Page | Route | Roles | Template | Backend |
|---|---|---|---|---|
| Landing | `/` | public | `shared/landing.html` | B1 |
| Login | `/login` | public | `shared/login.html` | B1 |
| Register | `/register` | public | `shared/register.html` | B1 |
| No access | 403 | any | `shared/403.html` | B1 |
| Error | 404 and 500 | any | `shared/error.html` | B1 |
| Driver: current assignment | `/driver` | driver | `driver/current.html` | B1 |
| Driver: trip history | `/driver/history` | driver | `driver/history.html` | B1 |

### F2: customer pages (7)

| Page | Route | Roles | Template | Backend |
|---|---|---|---|---|
| Dashboard | `/customer` | customer | `customer/dashboard.html` | B1 |
| Browse cars | `/vehicles` | customer | `customer/vehicles.html` | B1 |
| Car details | `/vehicles/<id>` | customer | `customer/vehicle_detail.html` | B1 |
| Rent form | `/rent/<vehicle_id>` | customer | `customer/rent.html` | B1 |
| Confirmation | `/rentals/<id>/confirmation` | customer | `customer/confirmation.html` | B1 |
| My rentals | `/my-rentals` | customer | `customer/my_rentals.html` | B2 |
| My profile | `/profile` | customer | `customer/profile.html` | B1 |

### F3: rental agent pages and the two reassign pages (9)

| Page | Route | Roles | Template | Backend |
|---|---|---|---|---|
| Agent dashboard | `/agent` | rental_agent | `agent/dashboard.html` | B2 |
| All rentals | `/agent/rentals` | rental_agent | `agent/rentals.html` | B2 |
| Rental details | `/agent/rentals/<id>` | rental_agent | `agent/rental_detail.html` | B2 |
| Walk-in rental | `/agent/rent` | rental_agent | `agent/walkin.html` | B1 |
| Process return | `/agent/rentals/<id>/return` | rental_agent | `agent/return.html` | B2 |
| Assign driver | `/agent/rentals/<id>/assign-driver` | rental_agent | `agent/assign_driver.html` | B1 |
| Customer lookup | `/agent/customers` | rental_agent | `agent/customers.html` | B2 |
| Change car or driver | `/fleet/rentals/<id>/reassign` | fleet_manager | `fleet/reassign.html` | B1 |
| Assignment history | `/fleet/assignment-history` | fleet_manager | `fleet/assignment_history.html` | B1 |

### F4: fleet manager pages (9)

| Page | Route | Roles | Template | Backend |
|---|---|---|---|---|
| Fleet dashboard | `/fleet` | fleet_manager | `fleet/dashboard.html` | B2 |
| Car list | `/fleet/vehicles` | fleet_manager | `fleet/vehicles.html` | B2 |
| Add car | `/fleet/vehicles/new` | fleet_manager | `fleet/vehicle_form.html` | B2 |
| Edit car | `/fleet/vehicles/<id>/edit` | fleet_manager | `fleet/vehicle_form.html` | B2 |
| Insurance | `/fleet/insurance` | fleet_manager | `fleet/insurance.html` | B2 |
| Maintenance list | `/fleet/maintenance` | fleet_manager | `fleet/maintenance.html` | B2 |
| Schedule maintenance | `/fleet/maintenance/new` | fleet_manager | `fleet/maintenance_form.html` | B2 |
| Driver list | `/fleet/drivers` | fleet_manager | `fleet/drivers.html` | B2 |
| Add or edit driver | `/fleet/drivers/new`, `/fleet/drivers/<id>/edit` | fleet_manager | `fleet/driver_form.html` | B2 |

The add and edit pages share one template each, so the 32 pages come from 34 routes.

---

## 11. API_CONTRACT.md

A plain text file listing, for every page, what the backend and frontend have promised each other. It exists because frontend people build pages before the backend does. If they guess a variable like `car.name` and the backend sends `vehicle.Make`, nothing shows and everyone argues. The contract fixes the names in advance.

**B1 writes it in the first two days.**

Each entry has the same shape:

```
### Process return
Route:        GET /agent/rentals/<id>/return
Who can open: Rental Agent
Page gets:    rental.Rental_ID, rental.Rental_Date, rental.Due_Date,
              vehicle.Make, vehicle.Model, vehicle.Daily_Rate,
              customer.First_Name, customer.Last_Name,
              today, days_late, late_fee, amount_due
Form sends:   POST /agent/rentals/<id>/return
              return_date
After submit: goes to /agent/rentals/<id>
Errors:       'Rental already returned' shown as a red flash message
```

**Rules:**
1. Nobody renames a variable without updating the file first and telling the person it affects.
2. If something is unclear, ask in the file. Do not guess.
3. A variable name in the contract is a promise. Add new ones freely, but never remove or rename an existing one without agreement.

---

## 12. Frontend guide

### Work in two stages

1. **Static stage (no backend needed).** Build your pages as plain `.html` files with fake hardcoded data and open them in the browser (VS Code Live Server helps). Use F1's `main.css` once it exists.
2. **Template stage.** When the backend route exists, turn the fake data into Jinja tags and move the file into `app/templates/<your folder>/`.

### The only Jinja you need

```html
{% extends 'shared/base.html' %}

{% block content %}
  <h1>Available cars</h1>

  {% for v in vehicles %}
    <div class="card">
      <h2>{{ v.Make }} {{ v.Model }}</h2>
      <p>KES {{ v.Daily_Rate }} per day</p>
      <a class="btn" href="{{ url_for('rent.rent', vehicle_id=v.Vehicle_ID) }}">Rent</a>
    </div>
  {% else %}
    <p>No cars available right now.</p>
  {% endfor %}

  {% if current_user.role == 'customer' %}
    <p>Your tier: {{ customer.Tier }}</p>
  {% endif %}
{% endblock %}
```

| Tag | Use |
|---|---|
| `{{ value }}` | Show a value |
| `{% for x in list %}` ... `{% endfor %}` | Repeat something (add `{% else %}` for an empty list) |
| `{% if %}` ... `{% endif %}` | Show something only sometimes |
| `{{ url_for('blueprint.function', id=3) }}` | Build a link. Do not hardcode URLs |
| `{% extends 'shared/base.html' %}` | Put your page inside F1's frame |

Variable names follow the database column names (`Daily_Rate`, `Tier`) unless `API_CONTRACT.md` says otherwise.

### Forms

Every form must include the CSRF token or it will be rejected:

```html
<form method="post">
  {{ form.hidden_tag() }}
  {{ form.start_date.label }} {{ form.start_date(class='input') }}
  <button class="btn" type="submit">Rent</button>
</form>
```

### CSS rules

- F1 owns `static/css/main.css`: colors, fonts, spacing, buttons (`btn`), boxes (`card`), forms (`input`), tables (`table`), badges and flash messages. Use these class names instead of inventing your own.
- Page-specific parts go in your own file under `static/css/components/`, for example `vehicle-card.css`. F1's `base.html` loads them.
- Suggested ownership of components: F2 the car card and tier badge, F3 the data table and confirm pop-up, F4 the status badge and form layout. F1 keeps the menu and flash messages.
- Design for a phone first. Many users will open this on a phone.
- Colors and spacing come from CSS variables defined in `main.css`, so one change restyles the whole site.

### JavaScript (small)

Plain JS in `static/js/`, no libraries. Two uses: the live price preview on the rent form (read dates and daily rate, show the estimate) and confirm pop-ups before destructive actions. The server always recalculates the price, so the preview is only a convenience.

### F1 starter kit

F1 ships a rough `base.html` and basic `main.css` within the first 2 or 3 days, even if ugly, so everyone else can build on it. Polish happens in week 2.

---

## 13. Team and ownership

Two backend (B1, B2) and four frontend (F1 to F4).

| Slot | Person | Area |
|---|---|---|
| B1 | Tallam | Login, booking, driver assignment, API contract |
| B2 | | Database, returns, fleet |
| F1 | | Shared design, public pages, driver pages |
| F2 | | Customer pages |
| F3 | | Rental agent pages and the two reassign pages |
| F4 | | Fleet manager pages |

### One rental from start to finish

1. Amina registers and logs in. (B1 logic, F1 pages)
2. She browses cars and rents a Corolla for 3 days with a chauffeur. (B1 logic, F2 pages)
3. An agent assigns her a driver, James. (B1 logic, F3 pages)
4. James logs in and sees the car and pickup details. (B1 logic, F1 pages)
5. Three days later the agent processes the return, the late fee is worked out and her tier updates. (B2 logic, F3 pages)
6. Before any of this, the manager added the Corolla and its insurance. (B2 logic, F4 pages)

### B1: login, booking and driver assignment

**In one line:** everything about who the user is and how a rental is created or changed.

**Builds:** app skeleton, DB connection, error handling, `API_CONTRACT.md`; register, login, logout, role checks; customer dashboard and profile; browse, car details, rent form with price and discount, create rental, confirmation, walk-in rental; assign driver, change car or driver with history logging, history page; the driver's own routes.

**Done when:** a customer can register, log in and rent a car, and an agent can give that rental a driver.

### B2: database, returns and fleet

**In one line:** stores everything and handles what happens after the car comes back.

**Builds:** final `schema.sql`, `seed.sql`, `seed_users.py`; the loyalty trigger; return a car, late fee, car back to available; my rentals, agent dashboard, all rentals, rental details, customer lookup; fleet routes (cars, insurance, maintenance, driver pool); one SQL test per business rule.

**Done when:** returning a car late charges the right fee, the tier updates and every rule has a passing test.

**Shared files:** B1 writes `is_vehicle_available` and `is_driver_free` in `rules.py`, and B2 writes `has_active_maintenance`. Agree on the rule signatures on day 0.

### F1: shared design, public pages and driver pages

**In one line:** makes the site look like one product.

**Builds:** `base.html` (header, menu, footer), the role-aware menu, `main.css`, landing, login, register, 403 and error pages, the two driver pages.

**Done when:** others can build a page using only your CSS classes and it looks right. If still overloaded after week 1, hand the two driver pages to whoever finishes first.

### F2: customer pages

**Builds:** dashboard, browse, car details, rent form (with the live price), confirmation, my rentals, my profile.

**Done when:** a customer can find a car, see the price and view their rentals.

### F3: rental agent pages

**Builds:** agent dashboard, all rentals with search, rental details, walk-in rental, return screen (days late, late fee, total), assign driver, customer lookup, plus the manager-only reassign and history pages.

**Done when:** an agent can find a rental, process its return and see the total.

### F4: fleet manager pages

**Builds:** fleet dashboard, car list, add and edit car, insurance, maintenance list, schedule maintenance, driver list, add and edit driver.

**Done when:** a manager can add a car, record its insurance and schedule maintenance.

### Who to ask

- F1 asks B1.
- F2 asks B1.
- F3 asks B1 for rent and assign driver, and B2 for returns.
- F4 asks B2, and B1 for the change-car screen.

### Rules for everyone

- Work on your own branch and only edit your own files.
- Pull from `main` every day.
- Open a pull request when a feature works. Tallam reviews.
- Need something from someone else? Ask them. Do not edit their file.
- Anyone who finishes early helps B2 with tests, seed data, the ER diagram and the report.

---

## 14. Git workflow

- `main` always runs. Nobody pushes to it directly.
- One branch per feature, named like `feature/rent-form`.
- Never commit `.env` or `venv/`.

```bash
git checkout main
git pull origin main
git checkout -b feature/rent-form

# ...do your work...

git add .
git commit -m "Add rent form page"
git push origin feature/rent-form
```

Then open a pull request on GitHub. Tallam reviews and merges it. Keep pull requests small, one feature each. If git says your branch is behind, run `git pull origin main` and fix any conflicts before pushing again.

---

## 15. Timeline

**Day 0, all together:** agree on this README, B2 publishes and freezes the 9-table schema, B1 starts `API_CONTRACT.md`.

**Week 1**
- B1: app skeleton, register, login, role check, browse, rent.
- B2: schema, seed data, loyalty trigger, returns, first tests.
- F1: rough `base.html` and `main.css` within 2 or 3 days.
- F2, F3, F4: static pages with fake data.

**Week 2**
- B1: walk-in, assign driver, change car or driver, history, driver routes.
- B2: fleet, maintenance, driver pool, remaining tests, my rentals and agent lists.
- F1 to F4: convert pages to templates and test against the real routes.

**Final days:** run the demo checks, polish the site, fix bugs, compile the report, rehearse the demo.

---

## 16. Testing

### One test per rule

B2 writes each as a SQL script in `tests/`. Each one runs the bad action and confirms it is blocked (or the good action gives the right number).

| Rule | Test | Expected |
|---|---|---|
| R1 | Insert a car with an existing VIN | Rejected by `UNIQUE` |
| R2 | Rent with an expired license | Blocked |
| R3 | Rent a car with expired insurance | Blocked |
| R3 | Rent a car whose status is `rented` | Blocked |
| R4 | Schedule maintenance on a car with an `in_progress` job | Blocked |
| R4 | Schedule maintenance on a `rented` car | Blocked |
| R5 | Assign a driver who has an open rental | Blocked |
| R6 | Return 2 days late on a 3,500 per day car | Late fee 10,500 |
| R7 | Complete the 5th rental for a customer | Tier becomes silver |
| R7 | Complete the 10th rental | Tier becomes gold |
| R8 | Silver customer returns late | Late fee has no discount applied |
| R9 | Delete a car that has rentals | Rentals remain, `Vehicle_ID` is `NULL` |
| R10 | Change the car to an uninsured one | Blocked, no history row added |
| R10 | Change the car to a valid one | Succeeds, one `ASSIGNMENT_HISTORY` row added |

### Demo checks (all of us, together)

1. Rent a car, return it late, and confirm the late fee is right and the tier updates.
2. Try to rent a car with expired insurance. It must be blocked.
3. Try to assign a driver who is already on a rental. It must be blocked.
4. Log in as one driver and confirm you cannot see another driver's job.
5. Log in as a customer and open `/fleet`. You must get the no-access page.

---

## 17. Security checklist

- [ ] Passwords are stored only as hashes (`generate_password_hash`), never plain text
- [ ] Every route has `@role_required`, except the public ones (landing, login, register)
- [ ] Every form includes `form.hidden_tag()` (CSRF)
- [ ] All SQL uses `%s` placeholders, never string formatting
- [ ] Customers and drivers only ever load their own data, using the ID from the session, not the URL
- [ ] The server recalculates prices and rechecks the rules, never trusting the browser
- [ ] `.env` and `venv/` are in `.gitignore`
- [ ] `SECRET_KEY` is a long random string, not `dev-only-change-me`
- [ ] Demo passwords are changed before anything is shown outside the team

---

## 18. Troubleshooting

| Problem | Fix |
|---|---|
| `'cryptography' package is required for sha256_password or caching_sha2_password` | `pip install cryptography` |
| `Access denied for user` | Check `DB_USER` and `DB_PASSWORD` in `.env`, and that the user exists and has privileges |
| `Can't connect to MySQL server` | MySQL is not running (`sudo service mysql start`), or the host and port in `.env` are wrong |
| Connecting from Windows to MySQL in WSL2 fails | Set `bind-address = 0.0.0.0`, create the user with host `'%'`, try `127.0.0.1`, then the WSL2 IP |
| `CHECK` constraints seem to do nothing | MySQL is older than 8.0.16. Upgrade |
| Trigger script errors in Workbench | Keep the `DELIMITER $$` and `DELIMITER ;` lines, and run it as a separate script |
| `CSRF token missing` | The form lacks `{{ form.hidden_tag() }}` |
| Template shows nothing for a variable | The name does not match `API_CONTRACT.md`. Check spelling and capitalization (`Daily_Rate`, not `daily_rate`) |
| `flask` command not found | Activate the venv first: `source venv/bin/activate` |
| 403 on a page you should reach | You are logged in as the wrong role. Log out and use the right demo account |

---

## 19. Out of scope and future ideas

Not required for the course, so not planned: password reset, change-password page, email or SMS notifications, online payments (for example M-Pesa), multiple branches and one-way rentals, damage reports and deposits, and deployment. Any of these can be added later without changing the design above.

---

## 20. Glossary

| Word | Meaning |
|---|---|
| Route | A backend function that answers one web address |
| Template | An HTML page with gaps the backend fills in |
| Blueprint | A Flask way to keep each area's routes in its own file |
| RBAC | Role-based access control: what you can open depends on your role |
| Trigger | SQL that runs by itself when something changes in the database |
| Transaction | Several database changes that all succeed or all fail together |
| CRUD | Create, read, update, delete |
| Branch | Your own copy of the code to work in safely |
| Pull request (PR) | A request to merge your branch into `main` |
| venv | A private Python setup for this project |
| CSRF | An attack where another site tricks your browser into submitting a form. The token blocks it |
| 1NF | First normal form: no repeating columns, so phone numbers live in their own table |

