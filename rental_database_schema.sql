-- DriveDesk Rental Agent Pages: suggested relational database schema
-- MySQL 8+ / MariaDB. Adapt names and date/decimal rules to your team's requirements.
CREATE DATABASE IF NOT EXISTS car_rental_system;
USE car_rental_system;

CREATE TABLE app_users (
  user_id INT AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(120) NOT NULL,
  email VARCHAR(160) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('AGENT','MANAGER') NOT NULL DEFAULT 'AGENT',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE customers (
  customer_id INT AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(120) NOT NULL,
  phone VARCHAR(30) NOT NULL,
  driving_license_no VARCHAR(80) NOT NULL UNIQUE,
  email VARCHAR(160),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE vehicles (
  vehicle_id INT AUTO_INCREMENT PRIMARY KEY,
  registration_no VARCHAR(20) NOT NULL UNIQUE,
  make VARCHAR(60) NOT NULL,
  model VARCHAR(60) NOT NULL,
  daily_rate DECIMAL(10,2) NOT NULL CHECK (daily_rate >= 0),
  vehicle_status ENUM('AVAILABLE','RENTED','MAINTENANCE') NOT NULL DEFAULT 'AVAILABLE'
);

CREATE TABLE drivers (
  driver_id INT AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(120) NOT NULL,
  phone VARCHAR(30) NOT NULL,
  driving_license_no VARCHAR(80) NOT NULL UNIQUE,
  driver_status ENUM('AVAILABLE','ASSIGNED','INACTIVE') NOT NULL DEFAULT 'AVAILABLE'
);

CREATE TABLE rentals (
  rental_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  vehicle_id INT NOT NULL,
  agent_user_id INT NOT NULL,
  start_date DATE NOT NULL,
  due_date DATE NOT NULL,
  actual_return_date DATE NULL,
  rental_status ENUM('ACTIVE','OVERDUE','RETURNED','CANCELLED') NOT NULL DEFAULT 'ACTIVE',
  daily_rate_at_booking DECIMAL(10,2) NOT NULL CHECK (daily_rate_at_booking >= 0),
  base_amount DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK (base_amount >= 0),
  late_days INT NOT NULL DEFAULT 0 CHECK (late_days >= 0),
  late_fee_per_day DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK (late_fee_per_day >= 0),
  late_fee DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK (late_fee >= 0),
  total_amount DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
  notes TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_rental_customer FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
  CONSTRAINT fk_rental_vehicle FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
  CONSTRAINT fk_rental_agent FOREIGN KEY (agent_user_id) REFERENCES app_users(user_id),
  CONSTRAINT chk_rental_dates CHECK (due_date >= start_date),
  INDEX idx_rental_status_due (rental_status, due_date),
  INDEX idx_rental_customer (customer_id)
);

CREATE TABLE rental_driver_assignments (
  assignment_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  rental_id BIGINT NOT NULL,
  driver_id INT NOT NULL,
  assigned_by INT NOT NULL,
  assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  unassigned_at TIMESTAMP NULL,
  CONSTRAINT fk_assignment_rental FOREIGN KEY (rental_id) REFERENCES rentals(rental_id),
  CONSTRAINT fk_assignment_driver FOREIGN KEY (driver_id) REFERENCES drivers(driver_id),
  CONSTRAINT fk_assignment_user FOREIGN KEY (assigned_by) REFERENCES app_users(user_id),
  INDEX idx_assignment_rental (rental_id),
  INDEX idx_assignment_driver (driver_id)
);

CREATE TABLE rental_change_history (
  change_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  rental_id BIGINT NOT NULL,
  change_type ENUM('VEHICLE','DRIVER') NOT NULL,
  old_value VARCHAR(160),
  new_value VARCHAR(160) NOT NULL,
  reason VARCHAR(500) NOT NULL,
  changed_by INT NOT NULL,
  changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_change_rental FOREIGN KEY (rental_id) REFERENCES rentals(rental_id),
  CONSTRAINT fk_change_user FOREIGN KEY (changed_by) REFERENCES app_users(user_id),
  INDEX idx_change_rental_time (rental_id, changed_at)
);

-- Important implementation rules:
-- 1. Use parameterized SQL/prepared statements in the backend.
-- 2. Store password hashes, never plain-text passwords.
-- 3. Enforce manager permissions on the server for vehicle/driver changes.
-- 4. Use a database transaction when changing a vehicle/driver and writing history.
-- 5. Calculate late_days = GREATEST(0, DATEDIFF(actual_return_date, due_date)).
-- 6. Calculate late_fee = late_days * late_fee_per_day; total_amount = base_amount + late_fee
--    (add taxes, deposits, damage fees, and discounts only if your business rules require them).
-- 7. A production system should prevent overlapping active rentals for the same vehicle.
