from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from pymysql.err import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth import User, role_required
from app.db import query, transaction
from app.forms import LoginForm, RegisterForm

bp = Blueprint('accounts', __name__)

ROLE_HOME = {
    'customer': '/customer',
    'rental_agent': '/agent',
    'fleet_manager': '/fleet',
    'driver': '/driver',
}


def home_for_role(role):
    return ROLE_HOME.get(role, '/')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(home_for_role(current_user.role))

    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()

        if query('SELECT 1 FROM USER_ACCOUNT WHERE Email = %s', (email,), one=True):
            flash('Email already registered', 'error')
            return redirect(url_for('accounts.register'))
        if query('SELECT 1 FROM CUSTOMER WHERE Email = %s', (email,), one=True):
            flash('Email already registered', 'error')
            return redirect(url_for('accounts.register'))
        if query('SELECT 1 FROM CUSTOMER WHERE License_Number = %s',
                 (form.license_number.data,), one=True):
            flash('License number already used', 'error')
            return redirect(url_for('accounts.register'))
        if query('SELECT 1 FROM CUSTOMER WHERE National_ID = %s',
                 (form.national_id.data,), one=True):
            flash('National ID already used', 'error')
            return redirect(url_for('accounts.register'))

        password_hash = generate_password_hash(form.password.data)
        try:
            with transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO CUSTOMER
                           (National_ID, First_Name, Last_Name, Email,
                            License_Number, License_Expiry)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (form.national_id.data.strip(), form.first_name.data.strip(),
                         form.last_name.data.strip(), email,
                         form.license_number.data.strip(), form.license_expiry.data))
                    customer_id = cur.lastrowid
                    cur.execute(
                        """INSERT INTO USER_ACCOUNT
                           (Email, Password_Hash, Role, Customer_ID)
                           VALUES (%s, %s, 'customer', %s)""",
                        (email, password_hash, customer_id))
        except IntegrityError:
            flash('Email, national ID or license number already in use.', 'error')
            return redirect(url_for('accounts.register'))

        account = query('SELECT * FROM USER_ACCOUNT WHERE Email = %s', (email,), one=True)
        login_user(User(account))
        flash('Welcome! Your account is ready.', 'success')
        return redirect('/customer')

    return render_template('shared/register.html', form=form)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(home_for_role(current_user.role))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        account = query('SELECT * FROM USER_ACCOUNT WHERE Email = %s', (email,), one=True)
        if account is None or not check_password_hash(account['Password_Hash'],
                                                       form.password.data):
            flash('Wrong email or password', 'error')
            return redirect(url_for('accounts.login'))

        login_user(User(account))
        return redirect(home_for_role(account['Role']))

    return render_template('shared/login.html', form=form)


@bp.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.landing'))


@bp.route('/customer')
@role_required('customer')
def dashboard():
    customer_id = current_user.customer_id
    customer = query('SELECT * FROM CUSTOMER WHERE Customer_ID = %s',
                     (customer_id,), one=True)
    if customer is None:
        abort(403)

    active_rental = query(
        """SELECT r.Rental_ID, r.Due_Date, v.Make, v.Model, v.Plate_Number
           FROM RENTAL r
           JOIN VEHICLE v ON v.Vehicle_ID = r.Vehicle_ID
           WHERE r.Customer_ID = %s AND r.Return_Date IS NULL
           ORDER BY r.Due_Date
           LIMIT 1""",
        (customer_id,), one=True)
    recent_rentals = query(
        """SELECT r.Rental_ID, r.Rental_Date, r.Due_Date, v.Make, v.Model
           FROM RENTAL r
           JOIN VEHICLE v ON v.Vehicle_ID = r.Vehicle_ID
           WHERE r.Customer_ID = %s
           ORDER BY r.Rental_Date DESC, r.Rental_ID DESC
           LIMIT 5""",
        (customer_id,))
    available_cars = query(
        """SELECT v.Vehicle_ID, v.Make, v.Model, v.Year, v.Daily_Rate
           FROM VEHICLE v
           WHERE v.Status = 'available'
             AND EXISTS (SELECT 1 FROM INSURANCE_POLICY i
                         WHERE i.Vehicle_ID = v.Vehicle_ID
                           AND i.Expiry_Date > CURDATE())
           ORDER BY v.Daily_Rate
           LIMIT 3""")
    available_count = query(
        """SELECT COUNT(*) AS n FROM VEHICLE v
           WHERE v.Status = 'available'
             AND EXISTS (SELECT 1 FROM INSURANCE_POLICY i
                         WHERE i.Vehicle_ID = v.Vehicle_ID
                           AND i.Expiry_Date > CURDATE())""", one=True)['n']
    rental_count = query(
        'SELECT COUNT(*) AS n FROM RENTAL WHERE Customer_ID = %s',
        (customer_id,), one=True)['n']

    return render_template('customer/dashboard.html', customer=customer,
                           active_rental=active_rental,
                           recent_rentals=recent_rentals,
                           available_cars=available_cars,
                           available_count=available_count,
                           rental_count=rental_count)


@bp.route('/profile', methods=['GET', 'POST'])
@role_required('customer')
def profile():
    customer_id = current_user.customer_id
    customer = query('SELECT * FROM CUSTOMER WHERE Customer_ID = %s',
                     (customer_id,), one=True)
    if customer is None:
        abort(403)

    if request.method == 'POST':
        phones = [phone.strip() for phone in request.form.getlist('phones')
                  if phone.strip()]
        if any(len(phone) > 20 for phone in phones):
            flash('Phone numbers must be 20 characters or fewer', 'error')
            return redirect(url_for('accounts.profile'))
        if len(phones) != len(set(phones)):
            flash('Phone number must be unique for you', 'error')
            return redirect(url_for('accounts.profile'))

        try:
            with transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        'DELETE FROM CUSTOMER_PHONE WHERE Customer_ID = %s',
                        (customer_id,))
                    for phone in phones:
                        cur.execute(
                            'INSERT INTO CUSTOMER_PHONE (Customer_ID, Phone_Number) '
                            'VALUES (%s, %s)',
                            (customer_id, phone))
        except IntegrityError:
            flash('Phone number must be unique for you', 'error')
            return redirect(url_for('accounts.profile'))

        flash('Profile updated', 'success')
        return redirect(url_for('accounts.profile'))

    phones = [row['Phone_Number'] for row in query(
        'SELECT Phone_Number FROM CUSTOMER_PHONE WHERE Customer_ID = %s '
        'ORDER BY Phone_Number', (customer_id,))]
    return render_template('customer/profile.html', customer=customer,
                           phones=phones)
