# Car Rental System: Team Guide

Prepared by Tallam Brian for the CNS_DES group. Written in plain language so anyone can follow it.

> This guide follows the repo's `README.md`, which stays the single source of truth. If the two ever disagree, the README wins.

## 1. What are we building?

We are building a website for a car rental company. Customers can look at cars, rent one (with or without a driver) and see their rentals. Staff can hand cars out, take them back, look after the fleet and manage drivers.

Three features make ours different from a basic rental site:

- **Self-drive or chauffeur:** a customer can rent a car alone or with a driver.
- **Insurance tracking:** a car with expired insurance cannot be rented.
- **Loyalty tiers:** customers who rent often become Silver or Gold and get a discount.

## 2. The four kinds of users

| Role | Who they are | What they can do |
|---|---|---|
| Customer | Someone renting a car | Browse cars, rent, see their own rentals and tier |
| Rental Agent | Staff at the desk | Walk-in rentals, process returns, assign drivers, see all rentals |
| Fleet Manager | The owner of the cars | Manage cars, insurance, maintenance and the driver list, and change the car or driver on a rental |
| Driver | A chauffeur | See only their own assigned car and trips |

This is called RBAC (role-based access control). Every page checks your role before it opens. A customer who types `/fleet` in the browser gets a "no access" page. Hiding a menu link is not enough, the server must check too.

## 3. The tools we use

| Tool | What it is for |
|---|---|
| Python + Flask | The backend. It receives a request, talks to the database and sends back a page |
| HTML | The structure of each page (headings, forms, tables) |
| CSS | How the page looks (colors, spacing, buttons) |
| JavaScript (a little) | The live price on the rent form and "are you sure?" pop-ups |
| MySQL | The database where everything is stored |
| PyMySQL | Lets Flask talk to MySQL |
| Flask-Login | Remembers who is logged in |
| Flask-WTF | Protects our forms from fake submissions |
| python-dotenv | Keeps passwords out of the code, in a `.env` file |
| venv + requirements.txt | Gives everyone the same Python setup |
| Git + GitHub | Lets six people work on one project without overwriting each other |

We are not using an ORM (we write plain SQL so it matches the report) and not Bootstrap or Tailwind (we write our own CSS).

## 4. How the website works

Think of a restaurant. The browser is the customer, the backend is the kitchen, the database is the fridge and the template is the plate.

Example: Amina clicks **Browse cars**.

1. Her browser asks for the page `/vehicles`.
2. A Flask function (a route) runs. It asks MySQL for the cars that are available and insured.
3. Flask hands that list to a template, which is an HTML page with gaps in it.
4. The template fills the gaps and the finished page goes back to her browser.

A template looks like normal HTML with a few extra tags. Variable names match the database column names.

```html
{% for v in vehicles %}
  <div class="card">{{ v.Make }} {{ v.Model }}: KES {{ v.Daily_Rate }} per day</div>
{% endfor %}
```

Frontend people only need three tags: `{{ variable }}` to show a value, `{% for %}` to repeat something and `{% if %}` to show something only sometimes.

## 5. The database

Nine tables hold all our data. The database is named `car_rental`.

| Table | What it stores |
|---|---|
| VEHICLE | Every car: VIN, plate, make, model, year, daily rate, status |
| INSURANCE_POLICY | One policy per car, with an expiry date |
| CUSTOMER | Customer details, license number and expiry, loyalty tier |
| CUSTOMER_PHONE | A customer's phone numbers (they can have several) |
| DRIVER | The chauffeurs, with a status of available or assigned |
| USER_ACCOUNT | Logins: email, hashed password, role |
| RENTAL | Every rental: customer, car, optional driver, dates, total cost, late fee |
| MAINTENANCE | Service jobs for each car |
| ASSIGNMENT_HISTORY | A log of every time a car or driver was changed on a rental, who did it and why |

Two additions came after the first design: the `USER_ACCOUNT` table (for login and roles) and a `Total_Cost` column on `RENTAL` (the price saved when the rental is created). The final schema is frozen on day 0 so nobody builds on a table that later changes. The full script lives in `schema.sql`, and sample data lives in `seed.sql`.

## 6. The business rules

These are the rules the system must enforce. Each one becomes a test.

1. Every car has a unique VIN and plate number.
2. A customer needs a driving license that has not expired.
3. A car can only be rented if its status is available and its insurance has not expired.
4. A car can only have one active maintenance job, and cannot be scheduled for maintenance while it is rented out.
5. A driver can only be on one active rental at a time.
6. Late fee = days late x daily rate x 1.5.
7. Loyalty tier depends on completed rentals (table below).
8. The loyalty discount applies to the rental cost only, never to late fees.
9. Removing a car from the fleet must not delete its rental history.
10. Changing the car or driver on a rental must pass the same checks as a new rental, and must be logged.

| Tier | Completed rentals | Discount |
|---|---|---|
| Standard | 0 to 4 | 0% |
| Silver | 5 to 9 | 5% |
| Gold | 10 or more | 10% |

The database upgrades the tier automatically using a trigger, which is a small piece of SQL that runs by itself when a return is recorded.

### What changes when something happens

| Event | Done by | Car status | Driver status |
|---|---|---|---|
| Rental created | B1 | available to rented | chauffeur only: available to assigned |
| Car or driver changed | B1 | old car back to available (or maintenance), new car to rented | old driver to available, new driver to assigned |
| Return processed | B2 | rented to available | assigned to available |
| Maintenance started | B2 | to maintenance | none |
| Maintenance finished | B2 | to available | none |

## 7. How the money works

- **Total cost** = days x daily rate x (1 minus the discount). It is saved when the rental is created.
- **Late fee** is worked out when the car comes back.
- **Amount due** = total cost + late fee.

Example: a Corolla at KES 3,500 per day, rented for 3 days by a Silver customer.

- 3 x 3,500 = 10,500. The 5% discount is 525, so the total cost is 9,975.
- The car comes back 2 days late: 2 x 3,500 x 1.5 = 10,500 late fee.
- Amount due: 9,975 + 10,500 = 20,475.

B1 writes `Total_Cost`. B2 writes `Late_Fee`. Neither person edits the other's column.

## 8. The team: who does what

There are six people in two groups. Backend (B1, B2) is the engine: logins, rules, database and calculations. Frontend (F1 to F4) is everything people see and click.

| Slot | Person | Area |
|---|---|---|
| B1 | Tallam | Login, booking, driver assignment |
| B2 | (fill in) | Database, returns, fleet |
| F1 | (fill in) | Shared design and public pages, driver pages |
| F2 | (fill in) | Customer pages |
| F3 | (fill in) | Rental agent pages |
| F4 | (fill in) | Fleet manager pages |

### Amina's rental, from start to finish

1. Amina registers and logs in. (B1 builds the logic, F1 builds the pages)
2. She browses cars and rents a Corolla for 3 days with a chauffeur. (B1 logic, F2 pages)
3. An agent assigns her a driver, James. (B1 logic, F3 pages)
4. James logs in and sees "Corolla, KDA 123A, pick up Amina". (B1 logic, F1 pages)
5. Three days later the agent processes the return, the late fee is worked out and her tier is updated. (B2 logic, F3 pages)
6. Before all of this, the manager added the Corolla and its insurance. (B2 logic, F4 pages)

### Rules for everyone

- Work on your own branch and only edit your own files.
- Pull from `main` every day.
- Open a pull request when a feature works. Tallam reviews it.
- If you need something from someone else, ask them. Do not change their file.

### B1 (Tallam): login, booking and driver assignment

You build the part that decides who someone is and how a rental gets created or changed. Think of it as the front door and the booking desk.

**Builds:**

- The Flask app, the database connection and error handling.
- Register, login, logout and the role check.
- Customer dashboard and profile, browse cars, car details.
- The rent form with price preview and discount, create rental, confirmation and walk-in rental.
- Assign driver, change car or driver (with the history log) and the history page.
- The driver's own routes: current assignment and trip history.
- `API_CONTRACT.md` (explained in section 10).

**Done when:** a customer can register, log in and rent a car, and an agent can give that rental a driver.

### B2: database, returns and fleet

You build the part that stores everything and handles what happens after a car comes back. Think of the accountant and the garage manager.

**Builds:**

- The final `schema.sql` and sample data (`seed.sql`, `seed_users.py`).
- The loyalty tier trigger.
- Return a car, work out the late fee and set the car back to available.
- The rental lists for agents, rental details and customer lookup.
- Fleet routes: add and edit cars, insurance, maintenance and the driver list.
- One SQL test for every business rule in section 6.

**Done when:** returning a car late charges the right fee, the tier updates and every rule has a passing test.

### F1: shared design, public pages and driver pages

You make the whole site look like one product. Think of the frame, the paint and the signs of a building. Everyone else furnishes their own rooms.

**Builds:**

- `base.html`: one file with the header, menu and footer. Every page sits inside it.
- The menu: it shows different links for each role. The backend tells the page the role and you decide which links to show.
- `main.css`: the shared styles, like class `btn` for buttons and class `card` for boxes, so everything matches.
- Landing, login, register, no-access and error pages.
- The two driver pages.

**Done when:** other people can build a page using only your CSS classes and it looks right.

Your load is heavy at the start, because everyone else is waiting for your frame. Two things help:

1. In the first 2 or 3 days, ship a rough `base.html` and basic CSS. It can be ugly. Polish it in week 2.
2. Share the small pieces. Each person writes the CSS for the parts they use, in their own file under `static/css/components/`: F2 does the car card and tier badge, F3 the table and confirm pop-up, F4 the status badge and form layout. You keep `main.css`, the menu and the flash messages.

If you are still overloaded after week 1, hand the two driver pages to whoever finishes first.

### F2: customer pages

You build everything a customer sees. Think of the showroom.

**Builds:** dashboard, browse cars, car details, the rent form, confirmation, my rentals and my profile.

**You need:** HTML, CSS and a little JavaScript for the live price on the rent form.

**Done when:** a customer can find a car, see the price and view their rentals.

### F3: rental agent pages

You build the screens an agent uses at the desk all day. Think of the front-desk computer.

**Builds:** agent dashboard, all rentals with search, rental details, walk-in rental, the return screen (shows days late, late fee and total), assign driver, customer lookup, and two manager-only pages: change the car or driver, and the history of those changes.

**You need:** HTML, CSS, tables and forms.

**Done when:** an agent can find a rental, process its return and see the total.

### F4: fleet manager pages

You build the screens for looking after the cars and drivers. Think of the garage office.

**Builds:** fleet dashboard, car list, add and edit car, insurance, maintenance list, schedule maintenance, driver list, and add or edit driver.

**You need:** HTML, CSS and forms.

**Done when:** a manager can add a car, record its insurance and schedule maintenance.

### Who to ask

- F1 asks B1 (login pages).
- F2 asks B1.
- F3 asks B1 for rent and assign driver, and B2 for returns.
- F4 asks B2, and B1 for the change-car screen.

## 9. All 32 pages

Routes are provisional until B1 confirms them in `API_CONTRACT.md`.

### F1 (7 pages)

| Page | Route | Shows |
|---|---|---|
| Landing | `/` | Hero, a few cars, login and register buttons |
| Login | `/login` | Email, password, error message |
| Register | `/register` | Name, email, password, national ID, license number and expiry, several phone numbers |
| No access | none | "You do not have access" for the wrong role |
| Error | none | One page for 404 and 500 |
| Driver: current assignment | `/driver` | Current car, dates, customer name and phone, upcoming jobs |
| Driver: trip history | `/driver/history` | Past trips |

### F2 (7 pages)

| Page | Route | Shows |
|---|---|---|
| Dashboard | `/customer` | Tier badge, active rental, quick links |
| Browse cars | `/vehicles` | Available cars only, filter by make and price |
| Car details | `/vehicles/<id>` | Specs, daily rate, Rent button |
| Rent form | `/rent/<vehicle_id>` | Dates, self-drive or chauffeur, price with discount |
| Confirmation | `/rentals/<id>/confirmation` | Rental summary |
| My rentals | `/my-rentals` | Active and past rentals, late fee, total |
| My profile | `/profile` | Phone numbers, license number and expiry |

### F3 (9 pages)

| Page | Route | Shows |
|---|---|---|
| Agent dashboard | `/agent` | Returns due today, overdue rentals |
| All rentals | `/agent/rentals` | Searchable table with filters |
| Rental details | `/agent/rentals/<id>` | Customer, car, driver, dates, fees |
| Walk-in rental | `/agent/rent` | Pick or create a customer, car, dates, chauffeur option |
| Process return | `/agent/rentals/<id>/return` | Return date, days late, late fee, total |
| Assign driver | `/agent/rentals/<id>/assign-driver` | List of free drivers |
| Customer lookup | `/agent/customers` | Search customers, tier, history |
| Change car or driver (manager only) | `/fleet/rentals/<id>/reassign` | New car or driver, reason box |
| Assignment history (manager only) | `/fleet/assignment-history` | Log of every change |

### F4 (9 pages)

| Page | Route | Shows |
|---|---|---|
| Fleet dashboard | `/fleet` | Counts by status, insurance expiring soon |
| Car list | `/fleet/vehicles` | Table with status badges |
| Add car | `/fleet/vehicles/new` | VIN, plate, make, model, year, daily rate |
| Edit car | `/fleet/vehicles/<id>/edit` | Same form, filled in |
| Insurance | `/fleet/insurance` | Policies and expiry dates, add or renew |
| Maintenance list | `/fleet/maintenance` | Jobs by status |
| Schedule maintenance | `/fleet/maintenance/new` | Car, dates, description |
| Driver list | `/fleet/drivers` | Drivers and availability |
| Add or edit driver | `/fleet/drivers/new`, `/fleet/drivers/<id>/edit` | Name and license number |

## 10. What is API_CONTRACT.md?

It is a plain text file in the repo that lists, for every page, what the backend and the frontend have promised each other.

**Why we need it:** frontend people build pages before the backend exists. If they guess a name like `car.name` and the backend sends `vehicle.Make`, nothing shows up and everyone argues about whose fault it is. The contract fixes the names in advance.

Each entry says the route, who can open it, what data the page receives, what the form sends back and what happens after submit. Contract variable names match the database column names (`Daily_Rate`, `Tier`), except for values the code computes itself (like `days_late`). Example:

```
### Rent form
Route:        GET /rent/<vehicle_id>
Who can open: Customer
Page gets:    vehicle.Make, vehicle.Model, vehicle.Daily_Rate,
              customer.Tier, discount_percent
Form sends:   POST /rent/<vehicle_id>
              start_date, end_date, is_chauffeur (true or false)
After submit: goes to /rentals/<id>/confirmation
Errors:       "Vehicle not available" shown as a red message
```

Rental Agents do not use this page; they create walk-in rentals at `/agent/rent`.

**Rules:** B1 writes it in the first two days. Nobody renames a variable without updating the file first and telling the person it affects. If something is unclear, ask in the file, do not guess.

## 11. How the project folder looks

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
│   │   ├── rent.py            # browse, details, rent, confirmation, walk-in            (B1)
│   │   ├── assignments.py     # assign driver, reassign, history, driver portal          (B1)
│   │   ├── returns.py         # process return, rental lists and details                (B2)
│   │   └── fleet.py           # vehicles, insurance, maintenance, driver pool            (B2)
│   ├── templates/             # frontend pages
│   │   ├── shared/  customer/  agent/  fleet/  driver/
│   └── static/
│       ├── css/main.css       # shared styles                                            (F1)
│       ├── css/components/    # each person's own component CSS files
│       └── js/                # small scripts (price preview, confirm dialogs)
├── schema.sql                 # all tables, trigger                                      (B2)
├── seed.sql                   # sample cars, customers, drivers                          (B2)
├── seed_users.py              # creates login accounts with hashed passwords             (B2)
├── tests/                     # SQL test scripts, one per business rule                  (B2)
├── API_CONTRACT.md            # every page: route, roles, variables, form fields         (B1)
├── requirements.txt
├── .env.example
├── .gitignore
├── run.py
└── README.md
```

Each person works in their own folder, so we almost never edit the same file. The shared files are `base.html` and `main.css` (F1 only), and `db.py`, `auth.py`, `config.py` (B1 only).

## 12. Setting up on your computer

Each person runs their own copy of MySQL on their own computer and loads `schema.sql` and the sample data (B2 provides both). That way nobody breaks anyone else's data.

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
cp .env.example .env              # then edit .env with your MySQL details

# 5. Create the database and load sample data
mysql -u root -p < schema.sql
mysql -u root -p car_rental < seed.sql

# 6. Create login accounts (hashed passwords)
python seed_users.py

# 7. Run
flask --app run run --debug
```

Then open <http://127.0.0.1:5000> in your browser.

Frontend people can start before any of this works. Make plain `.html` files with fake data and open them in the browser (VS Code Live Server helps). Convert them to templates when the backend routes are ready.

## 13. How we use Git

- `main` always works. Nobody pushes straight to it.
- Each person makes a branch per feature, for example `feature/rent-form`.
- Never commit your `.env` file or the `venv` folder.

```bash
git checkout main
git pull origin main
git checkout -b feature/rent-form

# (do your work)

git add .
git commit -m "Add rent form page"
git push origin feature/rent-form
```

Then open a pull request on GitHub. Tallam reviews and merges it. Run `git pull origin main` every day so your branch does not drift.

## 14. Order of work

**Day 0, all together:** agree on the rules in this guide, B2 publishes the final 9-table schema and B1 starts `API_CONTRACT.md`.

**Week 1:**

- B1 builds the app skeleton, register, login, role check, browse and rent.
- B2 builds the database, the loyalty trigger, returns and the first tests.
- F1 ships the rough `base.html` and CSS within 2 or 3 days.
- F2, F3 and F4 build their pages as plain HTML with fake data.

**Week 2:**

- B1 finishes walk-in, assign, change car or driver, history and the driver routes.
- B2 finishes fleet, maintenance, driver list and the remaining tests.
- Frontend people turn their pages into templates and test them against the real routes.

**Final days:** run the checks below, polish the site and rehearse the demo.

## 15. Checks before the demo

These cross the work of both backend people, so test them together.

1. Rent a car, return it late, and confirm the late fee is right and the tier updates.
2. Try to rent a car with expired insurance. It must be blocked.
3. Try to assign a driver who is already on a rental. It must be blocked.
4. Log in as one driver and confirm you cannot see another driver's job.
5. Log in as a customer and open `/fleet`. You must get the no-access page.

## 16. Words you may hear

| Word | Meaning |
|---|---|
| Route | A backend function that answers one web address |
| Template | An HTML page with gaps the backend fills in |
| Blueprint | A Flask way to keep each person's routes in their own file |
| Branch | Your own copy of the code to work in safely |
| Pull request (PR) | Asking to merge your branch into main |
| RBAC | Role-based access control: what you can open depends on your role |
| Trigger | SQL that runs by itself when something happens in the database |
| Transaction | Several database changes that all succeed or all fail together |
| CRUD | Create, read, update, delete: the basic add, view, edit and remove actions |
| venv | A private Python setup for this project |
