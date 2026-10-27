from flask import Blueprint, render_template
from flask_login import current_user

from app.auth import role_required
from app.db import query

bp = Blueprint('driver', __name__)


@bp.route('/driver')
@role_required('driver')
def current():
    rental = query(
        """SELECT r.Rental_ID, r.Rental_Date, r.Due_Date,
                  c.Customer_ID, c.First_Name, c.Last_Name,
                  v.Make, v.Model, v.Plate_Number
           FROM RENTAL r
           JOIN CUSTOMER c ON c.Customer_ID = r.Customer_ID
           LEFT JOIN VEHICLE v ON v.Vehicle_ID = r.Vehicle_ID
           WHERE r.Driver_ID = %s AND r.Return_Date IS NULL
           ORDER BY r.Due_Date, r.Rental_ID
           LIMIT 1""",
        (current_user.driver_id,),
        one=True,
    )

    customer_phone = None
    if rental is not None:
        phone = query(
            """SELECT Phone_Number FROM CUSTOMER_PHONE
               WHERE Customer_ID = %s
               ORDER BY Phone_Number
               LIMIT 1""",
            (rental['Customer_ID'],),
            one=True,
        )
        customer_phone = phone['Phone_Number'] if phone else None

    current_id = rental['Rental_ID'] if rental else 0
    upcoming = query(
        """SELECT r.Rental_ID, r.Rental_Date, r.Due_Date, v.Make, v.Model
           FROM RENTAL r
           LEFT JOIN VEHICLE v ON v.Vehicle_ID = r.Vehicle_ID
           WHERE r.Driver_ID = %s AND r.Return_Date IS NULL
             AND r.Rental_Date > CURDATE()
             AND r.Rental_ID <> %s
           ORDER BY r.Rental_Date, r.Rental_ID""",
        (current_user.driver_id, current_id),
    )

    return render_template(
        'driver/current.html',
        rental=rental,
        customer_phone=customer_phone,
        upcoming=upcoming,
    )


@bp.route('/driver/history')
@role_required('driver')
def history():
    trips = query(
        """SELECT r.Rental_ID, r.Rental_Date, r.Due_Date, r.Return_Date,
                  v.Make, v.Model, v.Plate_Number
           FROM RENTAL r
           LEFT JOIN VEHICLE v ON v.Vehicle_ID = r.Vehicle_ID
           WHERE r.Driver_ID = %s AND r.Return_Date IS NOT NULL
           ORDER BY r.Return_Date DESC, r.Rental_ID DESC""",
        (current_user.driver_id,),
    )
    return render_template('driver/history.html', trips=trips)
