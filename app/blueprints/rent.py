from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from pymysql.err import IntegrityError

from app.auth import role_required
from app.config import TIER_DISCOUNTS
from app.db import execute, query, transaction
from app.forms import RentForm
from app.services.pricing import rental_days, total_cost
from app.services.rules import customer_license_valid, is_driver_free, is_vehicle_available

bp = Blueprint('rent', __name__)


@bp.route('/vehicles')
@role_required('customer')
def vehicles():
    make = (request.args.get('make') or '').strip()
    max_price = request.args.get('max_price', type=float)

    sql = """SELECT v.Vehicle_ID, v.VIN, v.Plate_Number, v.Make, v.Model, v.Year,
                    v.Daily_Rate, v.Status
             FROM VEHICLE v
             WHERE v.Status = 'available'
               AND EXISTS (SELECT 1 FROM INSURANCE_POLICY i
                           WHERE i.Vehicle_ID = v.Vehicle_ID
                             AND i.Expiry_Date > CURDATE())"""
    params = []
    if make:
        sql += ' AND v.Make LIKE %s'
        params.append('%' + make + '%')
    if max_price is not None:
        sql += ' AND v.Daily_Rate <= %s'
        params.append(max_price)
    sql += ' ORDER BY v.Make, v.Model'

    return render_template('customer/vehicles.html',
                           vehicles=query(sql, tuple(params)))


@bp.route('/vehicles/<int:vehicle_id>')
@role_required('customer')
def vehicle_detail(vehicle_id):
    vehicle = query('SELECT * FROM VEHICLE WHERE Vehicle_ID = %s',
                    (vehicle_id,), one=True)
    if vehicle is None:
        abort(404)
    return render_template('customer/vehicle_detail.html', vehicle=vehicle)


@bp.route('/rent/<int:vehicle_id>', methods=['GET', 'POST'])
@role_required('customer')
def rent(vehicle_id):
    vehicle = query('SELECT * FROM VEHICLE WHERE Vehicle_ID = %s',
                    (vehicle_id,), one=True)
    if vehicle is None:
        abort(404)

    customer = query('SELECT * FROM CUSTOMER WHERE Customer_ID = %s',
                     (current_user.customer_id,), one=True)
    if customer is None:
        abort(403)

    form = RentForm()
    if form.validate_on_submit():
        if not customer_license_valid(customer['Customer_ID']):
            flash('Your driving license has expired', 'error')
        elif not is_vehicle_available(vehicle_id):
            flash('Vehicle not available', 'error')
        elif form.end_date.data < form.start_date.data:
            flash('End date cannot be before start date', 'error')
        else:
            days = rental_days(form.start_date.data, form.end_date.data)
            cost = total_cost(vehicle['Daily_Rate'], days, customer['Tier'])
            with transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO RENTAL
                           (Customer_ID, Vehicle_ID, Is_Chauffeur,
                            Rental_Date, Due_Date, Total_Cost)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (customer['Customer_ID'], vehicle_id, form.is_chauffeur.data,
                         form.start_date.data, form.end_date.data, cost))
                    rental_id = cur.lastrowid
                    cur.execute(
                        "UPDATE VEHICLE SET Status = 'rented' WHERE Vehicle_ID = %s",
                        (vehicle_id,))
            return redirect(url_for('rent.confirmation', rental_id=rental_id))

    discount_percent = int(TIER_DISCOUNTS[customer['Tier']] * 100)
    return render_template('customer/rent.html', vehicle=vehicle, customer=customer,
                           form=form, discount_percent=discount_percent,
                           today=date.today())


@bp.route('/rentals/<int:rental_id>/confirmation')
@role_required('customer')
def confirmation(rental_id):
    rental = query(
        'SELECT * FROM RENTAL WHERE Rental_ID = %s AND Customer_ID = %s',
        (rental_id, current_user.customer_id), one=True)
    if rental is None:
        abort(404)

    vehicle = (query('SELECT * FROM VEHICLE WHERE Vehicle_ID = %s',
                     (rental['Vehicle_ID'],), one=True)
               if rental['Vehicle_ID'] else None)
    driver = (query('SELECT * FROM DRIVER WHERE Driver_ID = %s',
                    (rental['Driver_ID'],), one=True)
              if rental['Driver_ID'] else None)

    return render_template('customer/confirmation.html', rental=rental,
                           vehicle=vehicle, driver=driver)


def walkin_page():
    customers = query(
        'SELECT Customer_ID, First_Name, Last_Name, Email, Tier '
        'FROM CUSTOMER ORDER BY First_Name, Last_Name')
    vehicles = query(
        """SELECT v.Vehicle_ID, v.Make, v.Model, v.Plate_Number, v.Daily_Rate
           FROM VEHICLE v
           WHERE v.Status = 'available'
             AND EXISTS (SELECT 1 FROM INSURANCE_POLICY i
                         WHERE i.Vehicle_ID = v.Vehicle_ID
                           AND i.Expiry_Date > CURDATE())
           ORDER BY v.Make, v.Model""")
    drivers = query(
        """SELECT d.Driver_ID, d.First_Name, d.Last_Name
           FROM DRIVER d
           WHERE d.Status = 'available'
             AND NOT EXISTS (SELECT 1 FROM RENTAL r
                             WHERE r.Driver_ID = d.Driver_ID
                               AND r.Return_Date IS NULL)
           ORDER BY d.First_Name, d.Last_Name""")
    return render_template('agent/walkin.html', customers=customers,
                           vehicles=vehicles, drivers=drivers)


@bp.route('/agent/rent', methods=['GET', 'POST'])
@role_required('rental_agent')
def walkin():
    if request.method == 'GET':
        return walkin_page()

    customer_id = request.form.get('customer_id', type=int)
    vehicle_id = request.form.get('vehicle_id', type=int)
    driver_id = request.form.get('driver_id', type=int)
    # Choosing a driver means the rental is chauffeured, even if the box was missed.
    is_chauffeur = request.form.get('is_chauffeur') == 'true' or driver_id is not None

    try:
        start_date = date.fromisoformat(request.form.get('start_date', ''))
        end_date = date.fromisoformat(request.form.get('end_date', ''))
    except ValueError:
        flash('Choose valid start and end dates.', 'error')
        return redirect(url_for('rent.walkin'))

    if end_date < start_date:
        flash('End date cannot be before start date.', 'error')
        return redirect(url_for('rent.walkin'))

    if not vehicle_id or not is_vehicle_available(vehicle_id):
        flash('Vehicle not available', 'error')
        return redirect(url_for('rent.walkin'))

    if driver_id is not None and not is_driver_free(driver_id):
        flash('Driver not available', 'error')
        return redirect(url_for('rent.walkin'))

    customer = None
    if customer_id:
        customer = query('SELECT * FROM CUSTOMER WHERE Customer_ID = %s',
                         (customer_id,), one=True)
        if customer is None:
            flash('Customer not found', 'error')
            return redirect(url_for('rent.walkin'))
        if not customer_license_valid(customer_id):
            flash('Customer license expired', 'error')
            return redirect(url_for('rent.walkin'))
    else:
        details = {
            'national_id': (request.form.get('national_id') or '').strip(),
            'first_name': (request.form.get('first_name') or '').strip(),
            'last_name': (request.form.get('last_name') or '').strip(),
            'email': (request.form.get('email') or '').strip(),
            'license_number': (request.form.get('license_number') or '').strip(),
            'license_expiry': (request.form.get('license_expiry') or '').strip(),
        }
        if not all(details.values()):
            flash('Fill in all details for the new customer.', 'error')
            return redirect(url_for('rent.walkin'))

        try:
            license_expiry = date.fromisoformat(details['license_expiry'])
        except ValueError:
            flash('Choose a valid license expiry date.', 'error')
            return redirect(url_for('rent.walkin'))

        if license_expiry <= date.today():
            flash('Customer license expired', 'error')
            return redirect(url_for('rent.walkin'))

        try:
            customer_id = execute(
                """INSERT INTO CUSTOMER
                   (National_ID, First_Name, Last_Name, Email,
                    License_Number, License_Expiry)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (details['national_id'], details['first_name'], details['last_name'],
                 details['email'], details['license_number'], license_expiry))
        except IntegrityError:
            flash('Email, national ID or license number already in use.', 'error')
            return redirect(url_for('rent.walkin'))

        customer = query('SELECT * FROM CUSTOMER WHERE Customer_ID = %s',
                         (customer_id,), one=True)

    vehicle = query('SELECT Daily_Rate FROM VEHICLE WHERE Vehicle_ID = %s',
                    (vehicle_id,), one=True)
    days = rental_days(start_date, end_date)
    cost = total_cost(vehicle['Daily_Rate'], days, customer['Tier'])

    rental_id = execute(
        """INSERT INTO RENTAL
           (Customer_ID, Vehicle_ID, Driver_ID, Is_Chauffeur,
            Rental_Date, Due_Date, Total_Cost)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (customer_id, vehicle_id, driver_id, is_chauffeur,
         start_date, end_date, cost))
    execute("UPDATE VEHICLE SET Status = 'rented' WHERE Vehicle_ID = %s", (vehicle_id,))
    if driver_id is not None:
        execute("UPDATE DRIVER SET Status = 'assigned' WHERE Driver_ID = %s", (driver_id,))

    flash('Rental created.', 'success')
    return redirect('/agent/rentals/%d' % rental_id)
