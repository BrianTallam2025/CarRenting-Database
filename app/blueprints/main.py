from flask import Blueprint, render_template

from app.db import query

bp = Blueprint('main', __name__)


@bp.route('/')
def landing():
    featured_vehicles = query(
        """SELECT v.Vehicle_ID, v.Make, v.Model, v.Year, v.Daily_Rate
           FROM VEHICLE v
           WHERE v.Status = 'available'
             AND EXISTS (SELECT 1 FROM INSURANCE_POLICY i
                         WHERE i.Vehicle_ID = v.Vehicle_ID
                           AND i.Expiry_Date > CURDATE())
           ORDER BY v.Daily_Rate
           LIMIT 3""")
    return render_template('shared/landing.html', featured_vehicles=featured_vehicles)
