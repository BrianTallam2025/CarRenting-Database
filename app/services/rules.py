from app.db import query


def is_vehicle_available(vehicle_id):
    row = query(
        """SELECT 1 FROM VEHICLE v
           JOIN INSURANCE_POLICY i ON i.Vehicle_ID = v.Vehicle_ID
           WHERE v.Vehicle_ID = %s AND v.Status = 'available'
             AND i.Expiry_Date > CURDATE()""",
        (vehicle_id,), one=True)
    return row is not None


def is_driver_free(driver_id):
    row = query(
        'SELECT 1 FROM RENTAL WHERE Driver_ID = %s AND Return_Date IS NULL',
        (driver_id,), one=True)
    return row is None


def has_active_maintenance(vehicle_id):
    row = query(
        "SELECT 1 FROM MAINTENANCE WHERE Vehicle_ID = %s AND Status = 'in_progress'",
        (vehicle_id,), one=True)
    return row is not None


def customer_license_valid(customer_id):
    row = query(
        'SELECT 1 FROM CUSTOMER WHERE Customer_ID = %s AND License_Expiry > CURDATE()',
        (customer_id,), one=True)
    return row is not None
