from datetime import date

import pymysql
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.auth import role_required
from app.db import get_db, query
from app.forms import ReturnForm
from app.services.pricing import late_fee, money

bp = Blueprint('returns', __name__)

RENTAL_SELECT = """SELECT r.*, v.Make, v.Model, v.Plate_Number,
                          c.First_Name AS Customer_First_Name,
                          c.Last_Name AS Customer_Last_Name,
                          d.First_Name AS Driver_First_Name,
                          d.Last_Name AS Driver_Last_Name
                   FROM RENTAL r
                   JOIN CUSTOMER c ON c.Customer_ID = r.Customer_ID
                   LEFT JOIN VEHICLE v ON v.Vehicle_ID = r.Vehicle_ID
                   LEFT JOIN DRIVER d ON d.Driver_ID = r.Driver_ID"""


def _search_pattern(value):
    return f'%{value.strip()}%'


def _rental_status(rental):
    if rental['Return_Date'] is not None:
        return 'returned'
    if rental['Due_Date'] < date.today():
        return 'overdue'
    return 'active'


def _amount_due(rental):
    return money((rental['Total_Cost'] or 0) + (rental['Late_Fee'] or 0))


def _rental_bundle(rental_id):
    rental = query(
        'SELECT * FROM RENTAL WHERE Rental_ID = %s',
        (rental_id,),
        one=True,
    )
    if rental is None:
        return None, None, None, None

    customer = query(
        'SELECT * FROM CUSTOMER WHERE Customer_ID = %s',
        (rental['Customer_ID'],),
        one=True,
    )
    vehicle = (
        query(
            'SELECT * FROM VEHICLE WHERE Vehicle_ID = %s',
            (rental['Vehicle_ID'],),
            one=True,
        )
        if rental['Vehicle_ID'] is not None
        else None
    )
    driver = (
        query(
            'SELECT * FROM DRIVER WHERE Driver_ID = %s',
            (rental['Driver_ID'],),
            one=True,
        )
        if rental['Driver_ID'] is not None
        else None
    )
    return rental, customer, vehicle, driver


@bp.route('/my-rentals')
@role_required('customer')
def my_rentals():
    rentals = query(
        """SELECT r.*, v.Make, v.Model, v.Plate_Number
           FROM RENTAL r
           LEFT JOIN VEHICLE v ON v.Vehicle_ID = r.Vehicle_ID
           WHERE r.Customer_ID = %s
           ORDER BY r.Rental_Date DESC, r.Rental_ID DESC""",
        (current_user.customer_id,),
    )
    for row in rentals:
        row['status'] = _rental_status(row)
        row['amount_due'] = _amount_due(row)
    return render_template('customer/my_rentals.html', rentals=rentals)


@bp.route('/agent')
@role_required('rental_agent')
def dashboard():
    counts = query(
        """SELECT
               (SELECT COUNT(*) FROM RENTAL WHERE Return_Date IS NULL) AS active,
               (SELECT COUNT(*) FROM RENTAL
                WHERE Return_Date IS NULL AND Due_Date = CURDATE()) AS due_today,
               (SELECT COUNT(*) FROM RENTAL
                WHERE Return_Date IS NULL AND Due_Date < CURDATE()) AS overdue,
               (SELECT COUNT(*) FROM VEHICLE WHERE Status = 'available') AS available""",
        one=True,
    )
    due_today = query(
        """SELECT r.Rental_ID, r.Due_Date,
                  c.First_Name AS Customer_First_Name,
                  c.Last_Name AS Customer_Last_Name,
                  v.Plate_Number
           FROM RENTAL r
           JOIN CUSTOMER c ON c.Customer_ID = r.Customer_ID
           LEFT JOIN VEHICLE v ON v.Vehicle_ID = r.Vehicle_ID
           WHERE r.Return_Date IS NULL AND r.Due_Date = CURDATE()
           ORDER BY r.Rental_ID"""
    )
    overdue = query(
        """SELECT r.Rental_ID, r.Due_Date,
                  DATEDIFF(CURDATE(), r.Due_Date) AS days_late,
                  c.First_Name AS Customer_First_Name,
                  c.Last_Name AS Customer_Last_Name,
                  v.Plate_Number
           FROM RENTAL r
           JOIN CUSTOMER c ON c.Customer_ID = r.Customer_ID
           LEFT JOIN VEHICLE v ON v.Vehicle_ID = r.Vehicle_ID
           WHERE r.Return_Date IS NULL AND r.Due_Date < CURDATE()
           ORDER BY r.Due_Date, r.Rental_ID"""
    )
    return render_template(
        'agent/dashboard.html',
        counts=counts,
        due_today=due_today,
        overdue=overdue,
    )


@bp.route('/agent/rentals')
@role_required('rental_agent')
def rentals():
    search = (request.args.get('search') or request.args.get('q') or '').strip()
    status = request.args.get('status', 'all')
    conditions = []
    params = []

    if status == 'active':
        conditions.append('r.Return_Date IS NULL AND r.Due_Date >= CURDATE()')
    elif status == 'overdue':
        conditions.append('r.Return_Date IS NULL AND r.Due_Date < CURDATE()')
    elif status == 'returned':
        conditions.append('r.Return_Date IS NOT NULL')
    if search:
        pattern = _search_pattern(search)
        conditions.append(
            """(CAST(r.Rental_ID AS CHAR) LIKE %s
                OR c.First_Name LIKE %s
                OR c.Last_Name LIKE %s
                OR c.Email LIKE %s
                OR v.Plate_Number LIKE %s)"""
        )
        params.extend([pattern] * 5)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ''
    rows = query(
        f"""{RENTAL_SELECT}
            {where}
            ORDER BY r.Rental_Date DESC, r.Rental_ID DESC
            LIMIT 200""",
        tuple(params),
    )
    for row in rows:
        row['status'] = _rental_status(row)
    return render_template(
        'agent/rentals.html',
        rentals=rows,
        search=search,
        status=status,
    )


@bp.route('/agent/rentals/<int:rental_id>')
@role_required('rental_agent', 'fleet_manager')
def rental_detail(rental_id):
    rental, customer, vehicle, driver = _rental_bundle(rental_id)
    if rental is None:
        abort(404)
    return render_template(
        'agent/rental_detail.html',
        rental=rental,
        customer=customer,
        vehicle=vehicle,
        driver=driver,
        amount_due=_amount_due(rental),
    )


@bp.route('/agent/rentals/<int:rental_id>/return', methods=['GET', 'POST'])
@role_required('rental_agent')
def process_return(rental_id):
    form = ReturnForm()
    if request.method == 'GET':
        form.return_date.data = date.today()

    rental, customer, vehicle, driver = _rental_bundle(rental_id)
    if rental is None:
        abort(404)

    if form.validate_on_submit():
        return_date = form.return_date.data
        if return_date > date.today():
            flash('The return date cannot be in the future.', 'error')
        elif return_date < rental['Rental_Date']:
            flash('The return date cannot be before the rental started.', 'error')
        elif rental['Return_Date'] is not None:
            flash('This rental has already been returned.', 'error')
        elif vehicle is None or vehicle['Daily_Rate'] is None:
            flash(
                'The vehicle record is missing, so the late fee cannot be calculated. '
                'Ask a manager to resolve the vehicle record before processing this return.',
                'error',
            )
        else:
            db = get_db()
            try:
                db.begin()
                with db.cursor() as cur:
                    cur.execute(
                        """SELECT r.Rental_ID, r.Return_Date, r.Rental_Date, r.Due_Date,
                                  r.Vehicle_ID, r.Driver_ID, v.Daily_Rate
                           FROM RENTAL r
                           LEFT JOIN VEHICLE v ON v.Vehicle_ID = r.Vehicle_ID
                           WHERE r.Rental_ID = %s
                           FOR UPDATE""",
                        (rental_id,),
                    )
                    locked_rental = cur.fetchone()
                    if locked_rental is None:
                        db.rollback()
                        abort(404)
                    if locked_rental['Return_Date'] is not None:
                        db.rollback()
                        flash('This rental has already been returned.', 'error')
                    elif return_date < locked_rental['Rental_Date']:
                        db.rollback()
                        flash('The return date cannot be before the rental started.', 'error')
                    elif locked_rental['Daily_Rate'] is None:
                        db.rollback()
                        flash(
                            'The vehicle record is missing, so the late fee cannot be '
                            'calculated. Ask a manager to resolve the vehicle record '
                            'before processing this return.',
                            'error',
                        )
                    else:
                        fee = late_fee(
                            locked_rental['Daily_Rate'],
                            locked_rental['Due_Date'],
                            return_date,
                        )
                        cur.execute(
                            """UPDATE RENTAL SET Return_Date = %s, Late_Fee = %s
                               WHERE Rental_ID = %s AND Return_Date IS NULL""",
                            (return_date, fee, rental_id),
                        )
                        if cur.rowcount != 1:
                            db.rollback()
                            flash('This rental has already been returned.', 'error')
                        else:
                            if locked_rental['Vehicle_ID'] is not None:
                                cur.execute(
                                    """SELECT 1 FROM MAINTENANCE
                                       WHERE Vehicle_ID = %s
                                         AND Status = 'in_progress'
                                       LIMIT 1""",
                                    (locked_rental['Vehicle_ID'],),
                                )
                                maintenance_is_active = cur.fetchone() is not None
                                vehicle_status = (
                                    'maintenance' if maintenance_is_active else 'available'
                                )
                                cur.execute(
                                    'UPDATE VEHICLE SET Status = %s WHERE Vehicle_ID = %s',
                                    (vehicle_status, locked_rental['Vehicle_ID']),
                                )

                            if locked_rental['Driver_ID'] is not None:
                                cur.execute(
                                    'SELECT Driver_ID FROM DRIVER WHERE Driver_ID = %s '
                                    'FOR UPDATE',
                                    (locked_rental['Driver_ID'],),
                                )
                                cur.execute(
                                    """SELECT 1 FROM RENTAL
                                       WHERE Driver_ID = %s AND Return_Date IS NULL
                                         AND Rental_ID <> %s
                                       LIMIT 1""",
                                    (locked_rental['Driver_ID'], rental_id),
                                )
                                if cur.fetchone() is None:
                                    cur.execute(
                                        """UPDATE DRIVER SET Status = 'available'
                                           WHERE Driver_ID = %s""",
                                        (locked_rental['Driver_ID'],),
                                    )
                            db.commit()
                            flash(
                                f'Return processed. Late fee: {fee:.2f}; amount due: '
                                f'{(rental["Total_Cost"] or 0) + fee:.2f}.',
                                'success',
                            )
                            return redirect(
                                url_for('returns.rental_detail', rental_id=rental_id)
                            )
            except pymysql.err.IntegrityError:
                db.rollback()
                flash('The return could not be saved because of a data conflict.', 'error')
            except Exception:
                db.rollback()
                raise

    rental, customer, vehicle, driver = _rental_bundle(rental_id)
    if rental['Return_Date'] is not None:
        display_date = rental['Return_Date']
        days_late = max(0, (display_date - rental['Due_Date']).days)
        preview_fee = rental['Late_Fee'] or money(0)
    else:
        display_date = form.return_date.data or date.today()
        preview_date = max(display_date, rental['Rental_Date'])
        days_late = max(0, (preview_date - rental['Due_Date']).days)
        preview_fee = (
            late_fee(vehicle['Daily_Rate'], rental['Due_Date'], preview_date)
            if vehicle and vehicle['Daily_Rate'] is not None
            else money(0)
        )
    amount_due = money((rental['Total_Cost'] or 0) + preview_fee)

    return render_template(
        'agent/return.html',
        rental=rental,
        customer=customer,
        vehicle=vehicle,
        form=form,
        today=display_date,
        days_late=days_late,
        late_fee=preview_fee,
        amount_due=amount_due,
    )


@bp.route('/agent/customers')
@role_required('rental_agent')
def customers():
    search = request.args.get('q', '').strip()
    params = ()
    where = ''
    if search:
        pattern = _search_pattern(search)
        where = """WHERE First_Name LIKE %s
                   OR Last_Name LIKE %s
                   OR Email LIKE %s
                   OR National_ID LIKE %s
                   OR License_Number LIKE %s"""
        params = (pattern,) * 5
    customer_rows = query(
        f"""SELECT Customer_ID, First_Name, Last_Name, Email, National_ID,
                   License_Number, License_Expiry, Tier
            FROM CUSTOMER {where}
            ORDER BY Last_Name, First_Name
            LIMIT 200""",
        params,
    )

    selected = None
    rentals = []
    selected_id = request.args.get('selected', type=int)
    if selected_id:
        selected = query(
            """SELECT Customer_ID, First_Name, Last_Name, Email, National_ID,
                      License_Number, License_Expiry, Tier
               FROM CUSTOMER WHERE Customer_ID = %s""",
            (selected_id,),
            one=True,
        )
        if selected:
            rentals = query(
                """SELECT r.Rental_ID, r.Rental_Date, r.Due_Date, v.Make, v.Model
                   FROM RENTAL r
                   LEFT JOIN VEHICLE v ON v.Vehicle_ID = r.Vehicle_ID
                   WHERE r.Customer_ID = %s
                   ORDER BY r.Rental_Date DESC, r.Rental_ID DESC""",
                (selected_id,),
            )

    return render_template(
        'agent/customers.html',
        customers=customer_rows,
        search=search,
        selected=selected,
        rentals=rentals,
    )
