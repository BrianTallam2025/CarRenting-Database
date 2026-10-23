from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from pymysql.err import IntegrityError

from app.auth import role_required
from app.db import execute, query
from app.services.pricing import rental_days, total_cost
from app.services.rules import customer_license_valid, is_driver_free, is_vehicle_available

bp = Blueprint('rent', __name__)


def walkin_page():
    customers = query(
        'SELECT Customer_ID, First_Name, Last_Name, Email, Tier '
        'FROM CUSTOMER ORDER BY First_Name, Last_Name')
    vehicles = query(
        """SELECT v.Vehicle_ID, v.Make, v.Model, v.Plate_Number, v.Daily_Rate
           FROM VEHICLE v
           JOIN INSURANCE_POLICY i ON i.Vehicle_ID = v.Vehicle_ID
           WHERE v.Status = 'available' AND i.Expiry_Date > CURDATE()
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
