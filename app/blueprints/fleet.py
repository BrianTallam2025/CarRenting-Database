from datetime import date, timedelta

import pymysql
from flask import Blueprint, abort, flash, redirect, render_template, url_for

from app.auth import role_required
from app.db import get_db, query
from app.forms import DriverForm, InsuranceForm, MaintenanceForm, VehicleForm
from app.services.rules import has_active_maintenance

bp = Blueprint('fleet', __name__)


def _vehicle_rows(include_rented=True):
    where = '' if include_rented else "WHERE Status <> 'rented'"
    return query(
        f"""SELECT Vehicle_ID, Make, Model, Plate_Number, Status
            FROM VEHICLE {where}
            ORDER BY Make, Model, Plate_Number"""
    )


def _vehicle_choices(vehicles):
    return [
        (
            row['Vehicle_ID'],
            f"{row['Make']} {row['Model']} ({row['Plate_Number']})",
        )
        for row in vehicles
    ]


@bp.route('/fleet')
@role_required('fleet_manager')
def dashboard():
    counts = {'available': 0, 'rented': 0, 'maintenance': 0}
    for row in query(
        """SELECT Status, COUNT(*) AS Count
           FROM VEHICLE GROUP BY Status"""
    ):
        counts[row['Status']] = row['Count']

    expiring_policies = query(
        """SELECT i.*, v.Make, v.Model, v.Plate_Number
           FROM INSURANCE_POLICY i
           JOIN VEHICLE v ON v.Vehicle_ID = i.Vehicle_ID
           WHERE i.Expiry_Date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY)
           ORDER BY i.Expiry_Date, v.Make, v.Model"""
    )
    return render_template(
        'fleet/dashboard.html',
        counts=counts,
        expiring_policies=expiring_policies,
    )


@bp.route('/fleet/vehicles')
@role_required('fleet_manager')
def vehicles():
    rows = query(
        """SELECT v.*, i.Provider, i.Expiry_Date
           FROM VEHICLE v
           LEFT JOIN INSURANCE_POLICY i ON i.Vehicle_ID = v.Vehicle_ID
           ORDER BY v.Make, v.Model, v.Plate_Number"""
    )
    return render_template('fleet/vehicles.html', vehicles=rows)


@bp.route('/fleet/vehicles/new', methods=['GET', 'POST'])
@role_required('fleet_manager')
def new_vehicle():
    form = VehicleForm()
    if form.validate_on_submit():
        try:
            db = get_db()
            with db.cursor() as cur:
                cur.execute(
                    """INSERT INTO VEHICLE
                       (VIN, Plate_Number, Make, Model, Year, Daily_Rate)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (
                        form.vin.data.strip().upper(),
                        form.plate_number.data.strip().upper(),
                        form.make.data.strip(),
                        form.model.data.strip(),
                        form.year.data,
                        form.daily_rate.data,
                    ),
                )
            db.commit()
        except pymysql.err.IntegrityError:
            get_db().rollback()
            flash('That VIN or plate number is already in the fleet.', 'error')
        except Exception:
            get_db().rollback()
            raise
        else:
            flash('Vehicle added.', 'success')
            return redirect(url_for('fleet.vehicles'))
    return render_template('fleet/vehicle_form.html', form=form, vehicle=None)


@bp.route('/fleet/vehicles/<int:vehicle_id>/edit', methods=['GET', 'POST'])
@role_required('fleet_manager')
def edit_vehicle(vehicle_id):
    vehicle = query(
        'SELECT * FROM VEHICLE WHERE Vehicle_ID = %s',
        (vehicle_id,),
        one=True,
    )
    if vehicle is None:
        abort(404)
    form = VehicleForm(obj=None)
    if not form.is_submitted():
        form.vin.data = vehicle['VIN']
        form.plate_number.data = vehicle['Plate_Number']
        form.make.data = vehicle['Make']
        form.model.data = vehicle['Model']
        form.year.data = vehicle['Year']
        form.daily_rate.data = vehicle['Daily_Rate']

    if form.validate_on_submit():
        db = get_db()
        try:
            db.begin()
            with db.cursor() as cur:
                cur.execute(
                    'SELECT Daily_Rate FROM VEHICLE WHERE Vehicle_ID = %s FOR UPDATE',
                    (vehicle_id,),
                )
                locked_vehicle = cur.fetchone()
                if locked_vehicle is None:
                    db.rollback()
                    abort(404)
                if form.daily_rate.data != locked_vehicle['Daily_Rate']:
                    cur.execute(
                        """SELECT 1 FROM RENTAL
                           WHERE Vehicle_ID = %s AND Return_Date IS NULL
                           LIMIT 1""",
                        (vehicle_id,),
                    )
                    if cur.fetchone():
                        db.rollback()
                        flash(
                            'The daily rate cannot be changed while the vehicle has '
                            'an active rental.',
                            'error',
                        )
                        return render_template(
                            'fleet/vehicle_form.html',
                            form=form,
                            vehicle=vehicle,
                        )
                cur.execute(
                    """UPDATE VEHICLE
                       SET VIN = %s, Plate_Number = %s, Make = %s, Model = %s,
                           Year = %s, Daily_Rate = %s
                       WHERE Vehicle_ID = %s""",
                    (
                        form.vin.data.strip().upper(),
                        form.plate_number.data.strip().upper(),
                        form.make.data.strip(),
                        form.model.data.strip(),
                        form.year.data,
                        form.daily_rate.data,
                        vehicle_id,
                    ),
                )
            db.commit()
        except pymysql.err.IntegrityError:
            db.rollback()
            flash('That VIN or plate number is already in the fleet.', 'error')
        except Exception:
            db.rollback()
            raise
        else:
            flash('Vehicle updated.', 'success')
            return redirect(url_for('fleet.vehicles'))
    return render_template('fleet/vehicle_form.html', form=form, vehicle=vehicle)


@bp.route('/fleet/insurance', methods=['GET', 'POST'])
@role_required('fleet_manager')
def insurance():
    vehicle_rows = _vehicle_rows()
    form = InsuranceForm()
    form.vehicle_id.choices = _vehicle_choices(vehicle_rows)
    if form.validate_on_submit():
        db = get_db()
        try:
            db.begin()
            with db.cursor() as cur:
                cur.execute(
                    'SELECT Policy_ID FROM INSURANCE_POLICY WHERE Vehicle_ID = %s '
                    'FOR UPDATE',
                    (form.vehicle_id.data,),
                )
                policy = cur.fetchone()
                if policy:
                    cur.execute(
                        """UPDATE INSURANCE_POLICY
                           SET Provider = %s, Expiry_Date = %s
                           WHERE Vehicle_ID = %s""",
                        (
                            form.provider.data.strip(),
                            form.expiry_date.data,
                            form.vehicle_id.data,
                        ),
                    )
                else:
                    cur.execute(
                        """INSERT INTO INSURANCE_POLICY
                           (Vehicle_ID, Provider, Expiry_Date)
                           VALUES (%s, %s, %s)""",
                        (
                            form.vehicle_id.data,
                            form.provider.data.strip(),
                            form.expiry_date.data,
                        ),
                    )
            db.commit()
        except pymysql.err.IntegrityError:
            db.rollback()
            flash('The insurance policy could not be saved because of a data conflict.', 'error')
        except Exception:
            db.rollback()
            raise
        else:
            flash('Insurance policy saved.', 'success')
            return redirect(url_for('fleet.insurance'))

    policies = query(
        """SELECT i.*, v.Make, v.Model, v.Plate_Number
           FROM INSURANCE_POLICY i
           JOIN VEHICLE v ON v.Vehicle_ID = i.Vehicle_ID
           ORDER BY i.Expiry_Date, v.Make, v.Model"""
    )
    today = date.today()
    for policy in policies:
        if policy['Expiry_Date'] < today:
            policy['status'] = 'expired'
        elif policy['Expiry_Date'] <= today + timedelta(days=30):
            policy['status'] = 'expiring'
        else:
            policy['status'] = 'valid'
    return render_template(
        'fleet/insurance.html',
        form=form,
        policies=policies,
        vehicles=vehicle_rows,
    )


@bp.route('/fleet/maintenance')
@role_required('fleet_manager')
def maintenance():
    jobs = query(
        """SELECT m.*, v.Make, v.Model, v.Plate_Number
           FROM MAINTENANCE m
           JOIN VEHICLE v ON v.Vehicle_ID = m.Vehicle_ID
           ORDER BY CASE m.Status
                       WHEN 'in_progress' THEN 1
                       WHEN 'scheduled' THEN 2
                       ELSE 3
                    END,
                    m.Start_Date DESC, m.Maintenance_ID DESC"""
    )
    return render_template('fleet/maintenance.html', jobs=jobs)


@bp.route('/fleet/maintenance/new', methods=['GET', 'POST'])
@role_required('fleet_manager')
def new_maintenance():
    vehicle_rows = _vehicle_rows(include_rented=False)
    form = MaintenanceForm()
    form.vehicle_id.choices = _vehicle_choices(vehicle_rows)
    if form.validate_on_submit():
        if form.end_date.data and form.end_date.data < form.start_date.data:
            flash('The expected end date cannot be before the start date.', 'error')
        else:
            db = get_db()
            try:
                db.begin()
                with db.cursor() as cur:
                    cur.execute(
                        'SELECT Status FROM VEHICLE WHERE Vehicle_ID = %s FOR UPDATE',
                        (form.vehicle_id.data,),
                    )
                    vehicle = cur.fetchone()
                    if vehicle is None:
                        db.rollback()
                        flash('The selected vehicle no longer exists.', 'error')
                    elif vehicle['Status'] == 'rented':
                        db.rollback()
                        flash('Maintenance cannot be scheduled for a rented vehicle.', 'error')
                    elif has_active_maintenance(form.vehicle_id.data):
                        db.rollback()
                        flash(
                            'This vehicle already has scheduled or active maintenance.',
                            'error',
                        )
                    else:
                        cur.execute(
                            """INSERT INTO MAINTENANCE
                               (Vehicle_ID, Status, Start_Date, End_Date, Description)
                               VALUES (%s, 'scheduled', %s, %s, %s)""",
                            (
                                form.vehicle_id.data,
                                form.start_date.data,
                                form.end_date.data,
                                form.description.data.strip(),
                            ),
                        )
                        db.commit()
                        flash('Maintenance scheduled.', 'success')
                        return redirect(url_for('fleet.maintenance'))
            except pymysql.err.IntegrityError:
                db.rollback()
                flash('Maintenance could not be scheduled because of a data conflict.', 'error')
            except Exception:
                db.rollback()
                raise
    return render_template(
        'fleet/maintenance_form.html',
        form=form,
        vehicles=vehicle_rows,
    )


@bp.route('/fleet/maintenance/<int:maintenance_id>/start', methods=['POST'])
@role_required('fleet_manager')
def start_maintenance(maintenance_id):
    db = get_db()
    try:
        db.begin()
        with db.cursor() as cur:
            cur.execute(
                """SELECT m.Vehicle_ID, m.Status AS Maintenance_Status, v.Status AS Vehicle_Status
                   FROM MAINTENANCE m
                   JOIN VEHICLE v ON v.Vehicle_ID = m.Vehicle_ID
                   WHERE m.Maintenance_ID = %s
                   FOR UPDATE""",
                (maintenance_id,),
            )
            job = cur.fetchone()
            if job is None:
                db.rollback()
                abort(404)
            if job['Maintenance_Status'] != 'scheduled':
                db.rollback()
                flash('Only scheduled maintenance can be started.', 'error')
            elif job['Vehicle_Status'] == 'rented':
                db.rollback()
                flash('Maintenance cannot start while the vehicle is rented.', 'error')
            else:
                cur.execute(
                    """SELECT 1 FROM MAINTENANCE
                       WHERE Vehicle_ID = %s AND Maintenance_ID <> %s
                         AND Status IN ('scheduled', 'in_progress')
                       LIMIT 1""",
                    (job['Vehicle_ID'], maintenance_id),
                )
                if cur.fetchone():
                    db.rollback()
                    flash('This vehicle already has another active maintenance job.', 'error')
                else:
                    cur.execute(
                        """UPDATE MAINTENANCE SET Status = 'in_progress'
                           WHERE Maintenance_ID = %s""",
                        (maintenance_id,),
                    )
                    cur.execute(
                        "UPDATE VEHICLE SET Status = 'maintenance' WHERE Vehicle_ID = %s",
                        (job['Vehicle_ID'],),
                    )
                    db.commit()
                    flash('Maintenance started.', 'success')
                    return redirect(url_for('fleet.maintenance'))
    except Exception:
        db.rollback()
        raise
    return redirect(url_for('fleet.maintenance'))


@bp.route('/fleet/maintenance/<int:maintenance_id>/complete', methods=['POST'])
@role_required('fleet_manager')
def complete_maintenance(maintenance_id):
    db = get_db()
    try:
        db.begin()
        with db.cursor() as cur:
            cur.execute(
                """SELECT m.Vehicle_ID, m.Status AS Maintenance_Status, m.Start_Date,
                          v.Status AS Vehicle_Status
                   FROM MAINTENANCE m
                   JOIN VEHICLE v ON v.Vehicle_ID = m.Vehicle_ID
                   WHERE m.Maintenance_ID = %s
                   FOR UPDATE""",
                (maintenance_id,),
            )
            job = cur.fetchone()
            if job is None:
                db.rollback()
                abort(404)
            if job['Maintenance_Status'] != 'in_progress':
                db.rollback()
                flash('Only in-progress maintenance can be completed.', 'error')
            elif job['Start_Date'] > date.today():
                db.rollback()
                flash('Future-dated maintenance cannot be completed yet.', 'error')
            else:
                cur.execute(
                    """UPDATE MAINTENANCE
                       SET Status = 'completed', End_Date = %s
                       WHERE Maintenance_ID = %s""",
                    (date.today(), maintenance_id),
                )
                cur.execute(
                    """SELECT 1 FROM MAINTENANCE
                       WHERE Vehicle_ID = %s AND Status = 'in_progress'
                       LIMIT 1""",
                    (job['Vehicle_ID'],),
                )
                other_active_job = cur.fetchone() is not None
                if not other_active_job and job['Vehicle_Status'] == 'maintenance':
                    cur.execute(
                        "UPDATE VEHICLE SET Status = 'available' WHERE Vehicle_ID = %s",
                        (job['Vehicle_ID'],),
                    )
                db.commit()
                flash('Maintenance completed.', 'success')
                return redirect(url_for('fleet.maintenance'))
    except Exception:
        db.rollback()
        raise
    return redirect(url_for('fleet.maintenance'))


@bp.route('/fleet/drivers')
@role_required('fleet_manager')
def drivers():
    driver_rows = query(
        """SELECT d.*,
                  (SELECT COUNT(*) FROM RENTAL r
                   WHERE r.Driver_ID = d.Driver_ID AND r.Return_Date IS NULL) AS Active_Rentals
           FROM DRIVER d
           ORDER BY d.Last_Name, d.First_Name"""
    )
    return render_template('fleet/drivers.html', drivers=driver_rows)


@bp.route('/fleet/drivers/new', methods=['GET', 'POST'])
@role_required('fleet_manager')
def new_driver():
    form = DriverForm()
    if form.validate_on_submit():
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute(
                    """INSERT INTO DRIVER (First_Name, Last_Name, License_Number)
                       VALUES (%s, %s, %s)""",
                    (
                        form.first_name.data.strip(),
                        form.last_name.data.strip(),
                        form.license_number.data.strip().upper(),
                    ),
                )
            db.commit()
        except pymysql.err.IntegrityError:
            db.rollback()
            flash('That driver license number is already registered.', 'error')
        except Exception:
            db.rollback()
            raise
        else:
            flash('Driver added.', 'success')
            return redirect(url_for('fleet.drivers'))
    return render_template('fleet/driver_form.html', form=form, driver=None)


@bp.route('/fleet/drivers/<int:driver_id>/edit', methods=['GET', 'POST'])
@role_required('fleet_manager')
def edit_driver(driver_id):
    driver = query(
        'SELECT * FROM DRIVER WHERE Driver_ID = %s',
        (driver_id,),
        one=True,
    )
    if driver is None:
        abort(404)
    form = DriverForm()
    if not form.is_submitted():
        form.first_name.data = driver['First_Name']
        form.last_name.data = driver['Last_Name']
        form.license_number.data = driver['License_Number']
    if form.validate_on_submit():
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute(
                    """UPDATE DRIVER
                       SET First_Name = %s, Last_Name = %s, License_Number = %s
                       WHERE Driver_ID = %s""",
                    (
                        form.first_name.data.strip(),
                        form.last_name.data.strip(),
                        form.license_number.data.strip().upper(),
                        driver_id,
                    ),
                )
            db.commit()
        except pymysql.err.IntegrityError:
            db.rollback()
            flash('That driver license number is already registered.', 'error')
        except Exception:
            db.rollback()
            raise
        else:
            flash('Driver updated.', 'success')
            return redirect(url_for('fleet.drivers'))
    return render_template('fleet/driver_form.html', form=form, driver=driver)
