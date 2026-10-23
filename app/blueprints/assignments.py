from flask import Blueprint, abort, flash, redirect, render_template, request
from flask_login import current_user

from app.auth import role_required
from app.db import execute, query
from app.services.rules import is_driver_free, is_vehicle_available

bp = Blueprint('assignments', __name__)


def free_drivers():
    return query(
        """SELECT d.Driver_ID, d.First_Name, d.Last_Name
           FROM DRIVER d
           WHERE d.Status = 'available'
             AND NOT EXISTS (SELECT 1 FROM RENTAL r
                             WHERE r.Driver_ID = d.Driver_ID
                               AND r.Return_Date IS NULL)
           ORDER BY d.First_Name, d.Last_Name""")


def available_vehicles():
    return query(
        """SELECT v.Vehicle_ID, v.Make, v.Model, v.Plate_Number, v.Daily_Rate
           FROM VEHICLE v
           JOIN INSURANCE_POLICY i ON i.Vehicle_ID = v.Vehicle_ID
           WHERE v.Status = 'available' AND i.Expiry_Date > CURDATE()
           ORDER BY v.Make, v.Model""")


@bp.route('/agent/rentals/<int:rental_id>/assign-driver', methods=['GET', 'POST'])
@role_required('rental_agent')
def assign_driver(rental_id):
    rental = query('SELECT * FROM RENTAL WHERE Rental_ID = %s', (rental_id,), one=True)
    if rental is None:
        abort(404)

    if request.method == 'POST':
        if rental['Return_Date'] is not None:
            flash('Rental already returned', 'error')
            return redirect('/agent/rentals/%d' % rental_id)

        driver_id = request.form.get('driver_id', type=int)
        if not driver_id:
            flash('Choose a driver.', 'error')
            return redirect('/agent/rentals/%d/assign-driver' % rental_id)

        if not is_driver_free(driver_id):
            flash('Driver is not available', 'error')
            return redirect('/agent/rentals/%d/assign-driver' % rental_id)

        old_driver_id = rental['Driver_ID']
        execute(
            'UPDATE RENTAL SET Driver_ID = %s, Is_Chauffeur = TRUE WHERE Rental_ID = %s',
            (driver_id, rental_id))
        if old_driver_id and old_driver_id != driver_id:
            execute("UPDATE DRIVER SET Status = 'available' WHERE Driver_ID = %s",
                    (old_driver_id,))
        execute("UPDATE DRIVER SET Status = 'assigned' WHERE Driver_ID = %s",
                (driver_id,))

        flash('Driver assigned.', 'success')
        return redirect('/agent/rentals/%d' % rental_id)

    return render_template('agent/assign_driver.html', rental=rental,
                           free_drivers=free_drivers())


@bp.route('/fleet/rentals/<int:rental_id>/reassign', methods=['GET', 'POST'])
@role_required('fleet_manager')
def reassign(rental_id):
    rental = query('SELECT * FROM RENTAL WHERE Rental_ID = %s', (rental_id,), one=True)
    if rental is None:
        abort(404)

    vehicle = (query('SELECT * FROM VEHICLE WHERE Vehicle_ID = %s',
                     (rental['Vehicle_ID'],), one=True)
               if rental['Vehicle_ID'] else None)
    driver = (query('SELECT * FROM DRIVER WHERE Driver_ID = %s',
                    (rental['Driver_ID'],), one=True)
              if rental['Driver_ID'] else None)

    if request.method == 'POST':
        if rental['Return_Date'] is not None:
            flash('Rental already returned', 'error')
            return redirect('/fleet/assignment-history')

        new_vehicle_id = request.form.get('vehicle_id', type=int) or rental['Vehicle_ID']
        new_driver_id = request.form.get('driver_id', type=int)
        if new_driver_id is None:
            new_driver_id = rental['Driver_ID']
        reason = (request.form.get('reason') or '').strip()

        if not reason:
            flash('Give a reason for the change.', 'error')
            return redirect('/fleet/rentals/%d/reassign' % rental_id)

        if new_vehicle_id != rental['Vehicle_ID'] and not is_vehicle_available(new_vehicle_id):
            flash('Vehicle not available', 'error')
            return redirect('/fleet/rentals/%d/reassign' % rental_id)

        if (new_driver_id is not None and new_driver_id != rental['Driver_ID']
                and not is_driver_free(new_driver_id)):
            flash('Driver not available', 'error')
            return redirect('/fleet/rentals/%d/reassign' % rental_id)

        if new_vehicle_id == rental['Vehicle_ID'] and new_driver_id == rental['Driver_ID']:
            flash('Nothing changed.', 'error')
            return redirect('/fleet/rentals/%d/reassign' % rental_id)

        old_vehicle_id = rental['Vehicle_ID']
        old_driver_id = rental['Driver_ID']

        execute('UPDATE RENTAL SET Vehicle_ID = %s, Driver_ID = %s WHERE Rental_ID = %s',
                (new_vehicle_id, new_driver_id, rental_id))
        if old_vehicle_id != new_vehicle_id:
            execute("UPDATE VEHICLE SET Status = 'available' WHERE Vehicle_ID = %s",
                    (old_vehicle_id,))
            execute("UPDATE VEHICLE SET Status = 'rented' WHERE Vehicle_ID = %s",
                    (new_vehicle_id,))
        if old_driver_id != new_driver_id:
            if old_driver_id:
                execute("UPDATE DRIVER SET Status = 'available' WHERE Driver_ID = %s",
                        (old_driver_id,))
            if new_driver_id:
                execute("UPDATE DRIVER SET Status = 'assigned' WHERE Driver_ID = %s",
                        (new_driver_id,))

        execute(
            """INSERT INTO ASSIGNMENT_HISTORY
               (Rental_ID, Old_Vehicle_ID, New_Vehicle_ID,
                Old_Driver_ID, New_Driver_ID, Changed_By, Reason)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (rental_id, old_vehicle_id, new_vehicle_id,
             old_driver_id, new_driver_id, current_user.id, reason))

        flash('Change saved.', 'success')
        return redirect('/fleet/assignment-history')

    return render_template('fleet/reassign.html', rental=rental, vehicle=vehicle,
                           driver=driver, available_vehicles=available_vehicles(),
                           free_drivers=free_drivers())


@bp.route('/fleet/assignment-history')
@role_required('fleet_manager')
def assignment_history():
    history = query(
        """SELECT h.History_ID, h.Rental_ID, h.Changed_At, h.Reason,
                  h.Old_Vehicle_ID, h.New_Vehicle_ID,
                  h.Old_Driver_ID, h.New_Driver_ID,
                  u.Email AS changed_by
           FROM ASSIGNMENT_HISTORY h
           JOIN USER_ACCOUNT u ON u.User_ID = h.Changed_By
           ORDER BY h.Changed_At DESC, h.History_ID DESC""")
    return render_template('fleet/assignment_history.html', history=history)
