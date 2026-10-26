from datetime import date

import pymysql
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.auth import role_required
from app.db import get_db, query
from app.forms import ReturnForm
from app.services.pricing import late_fee

bp = Blueprint('returns', __name__)

RENTAL_SELECT = """SELECT r.*, v.Make, v.Model, v.Plate_Number, v.Daily_Rate,
                          c.First_Name, c.Last_Name, c.Email AS Customer_Email,
                          d.First_Name AS Driver_First_Name,
                          d.Last_Name AS Driver_Last_Name
                   FROM RENTAL r
                   JOIN CUSTOMER c ON c.Customer_ID = r.Customer_ID
                   LEFT JOIN VEHICLE v ON v.Vehicle_ID = r.Vehicle_ID
                   LEFT JOIN DRIVER d ON d.Driver_ID = r.Driver_ID"""


def _search_pattern(value):
    return f'%{value.strip()}%'


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
    return render_template('customer/my_rentals.html', rentals=rentals)


@bp.route('/agent')
@role_required('rental_agent')
def dashboard():
    summary = query(
        """SELECT
               COALESCE(SUM(CASE WHEN Return_Date IS NULL THEN 1 ELSE 0 END), 0)
                   AS active_rentals,
               COALESCE(SUM(CASE WHEN Return_Date IS NULL AND Due_Date < CURDATE()
                                 THEN 1 ELSE 0 END), 0) AS overdue_rentals,
               COALESCE(SUM(CASE WHEN Return_Date >= CURDATE() THEN 1 ELSE 0 END), 0)
                   AS returned_today
           FROM RENTAL""",
        one=True,
    )
    recent_rentals = query(
        f"""{RENTAL_SELECT}
            ORDER BY r.Rental_ID DESC
            LIMIT 10"""
    )
    return render_template(
        'agent/dashboard.html',
        summary=summary,
        rentals=recent_rentals,
    )


@bp.route('/agent/rentals')
@role_required('rental_agent')
def rentals():
    search = request.args.get('q', '').strip()
    status = request.args.get('status', 'all')
    conditions = []
    params = []

    if status == 'active':
        conditions.append('r.Return_Date IS NULL')
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
    return render_template(
        'agent/rentals.html',
        rentals=rows,
        search=search,
        status=status,
    )


@bp.route('/agent/rentals/<int:rental_id>')
@role_required('rental_agent')
def rental_detail(rental_id):
    rental = query(
        f'{RENTAL_SELECT} WHERE r.Rental_ID = %s',
        (rental_id,),
        one=True,
    )
    if rental is None:
        abort(404)
    return render_template('agent/rental_detail.html', rental=rental)


@bp.route('/agent/rentals/<int:rental_id>/return', methods=['GET', 'POST'])
@role_required('rental_agent')
def process_return(rental_id):
    form = ReturnForm()
    if request.method == 'GET':
        form.return_date.data = date.today()

    rental = query(
        f'{RENTAL_SELECT} WHERE r.Rental_ID = %s',
        (rental_id,),
        one=True,
    )
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
        elif rental['Daily_Rate'] is None:
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
                                f'{rental["Total_Cost"] + fee:.2f}.',
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

        rental = query(
            f'{RENTAL_SELECT} WHERE r.Rental_ID = %s',
            (rental_id,),
            one=True,
        )

    return render_template('agent/return.html', rental=rental, form=form, today=date.today())


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
                   OR National_ID LIKE %s"""
        params = (pattern, pattern, pattern, pattern)
    customer_rows = query(
        f"""SELECT Customer_ID, First_Name, Last_Name, Email, National_ID,
                   License_Number, License_Expiry, Tier
            FROM CUSTOMER {where}
            ORDER BY Last_Name, First_Name
            LIMIT 200""",
        params,
    )
    return render_template(
        'agent/customers.html',
        customers=customer_rows,
        search=search,
    )
