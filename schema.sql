-- Car Rental System schema
-- Database name must match DB_NAME in .env (see README section 7)

CREATE DATABASE IF NOT EXISTS car_rental;
USE car_rental;

CREATE TABLE VEHICLE (
    Vehicle_ID    INT PRIMARY KEY AUTO_INCREMENT,
    VIN           VARCHAR(17) UNIQUE NOT NULL,
    Plate_Number  VARCHAR(15) UNIQUE NOT NULL,
    Make          VARCHAR(50) NOT NULL,
    Model         VARCHAR(50) NOT NULL,
    Year          INT NOT NULL,
    Daily_Rate    DECIMAL(10,2) NOT NULL,
    Status        VARCHAR(20) NOT NULL DEFAULT 'available'
                  CHECK (Status IN ('available', 'rented', 'maintenance'))
);

CREATE TABLE INSURANCE_POLICY (
    Policy_ID    INT PRIMARY KEY AUTO_INCREMENT,
    Vehicle_ID   INT NOT NULL UNIQUE,
    Provider     VARCHAR(100) NOT NULL,
    Expiry_Date  DATE NOT NULL,
    FOREIGN KEY (Vehicle_ID) REFERENCES VEHICLE(Vehicle_ID)
);

CREATE TABLE CUSTOMER (
    Customer_ID     INT PRIMARY KEY AUTO_INCREMENT,
    National_ID     VARCHAR(20) UNIQUE NOT NULL,
    First_Name      VARCHAR(50) NOT NULL,
    Last_Name       VARCHAR(50) NOT NULL,
    Email           VARCHAR(100) UNIQUE NOT NULL,
    License_Number  VARCHAR(30) UNIQUE NOT NULL,
    License_Expiry  DATE NOT NULL,
    Tier            VARCHAR(20) NOT NULL DEFAULT 'standard'
                    CHECK (Tier IN ('standard', 'silver', 'gold'))
);

CREATE TABLE CUSTOMER_PHONE (
    Customer_ID   INT,
    Phone_Number  VARCHAR(20),
    PRIMARY KEY (Customer_ID, Phone_Number),
    FOREIGN KEY (Customer_ID) REFERENCES CUSTOMER(Customer_ID) ON DELETE CASCADE
);

CREATE TABLE DRIVER (
    Driver_ID       INT PRIMARY KEY AUTO_INCREMENT,
    First_Name      VARCHAR(50) NOT NULL,
    Last_Name       VARCHAR(50) NOT NULL,
    License_Number  VARCHAR(30) UNIQUE NOT NULL,
    Status          VARCHAR(20) NOT NULL DEFAULT 'available'
                    CHECK (Status IN ('available', 'assigned'))
);

CREATE TABLE USER_ACCOUNT (
    User_ID        INT PRIMARY KEY AUTO_INCREMENT,
    Email          VARCHAR(100) UNIQUE NOT NULL,
    Password_Hash  VARCHAR(255) NOT NULL,
    Role           VARCHAR(20) NOT NULL
                   CHECK (Role IN ('customer', 'rental_agent', 'fleet_manager', 'driver')),
    Customer_ID    INT UNIQUE,
    Driver_ID      INT UNIQUE,
    FOREIGN KEY (Customer_ID) REFERENCES CUSTOMER(Customer_ID) ON DELETE CASCADE,
    FOREIGN KEY (Driver_ID)   REFERENCES DRIVER(Driver_ID)     ON DELETE CASCADE
);

CREATE TABLE RENTAL (
    Rental_ID     INT PRIMARY KEY AUTO_INCREMENT,
    Customer_ID   INT NOT NULL,
    Vehicle_ID    INT,
    Driver_ID     INT,
    Is_Chauffeur  BOOLEAN NOT NULL DEFAULT FALSE,
    Rental_Date   DATE NOT NULL,
    Due_Date      DATE NOT NULL,
    Return_Date   DATE,
    Total_Cost    DECIMAL(10,2) NOT NULL,
    Late_Fee      DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    FOREIGN KEY (Customer_ID) REFERENCES CUSTOMER(Customer_ID),
    FOREIGN KEY (Vehicle_ID)  REFERENCES VEHICLE(Vehicle_ID) ON DELETE SET NULL,
    FOREIGN KEY (Driver_ID)   REFERENCES DRIVER(Driver_ID)   ON DELETE SET NULL
);

CREATE TABLE MAINTENANCE (
    Maintenance_ID  INT PRIMARY KEY AUTO_INCREMENT,
    Vehicle_ID      INT NOT NULL,
    Status          VARCHAR(20) NOT NULL DEFAULT 'scheduled'
                    CHECK (Status IN ('scheduled', 'in_progress', 'completed')),
    Start_Date      DATE NOT NULL,
    End_Date        DATE,
    Description     VARCHAR(255),
    FOREIGN KEY (Vehicle_ID) REFERENCES VEHICLE(Vehicle_ID)
);

CREATE TABLE ASSIGNMENT_HISTORY (
    History_ID      INT PRIMARY KEY AUTO_INCREMENT,
    Rental_ID       INT NOT NULL,
    Old_Vehicle_ID  INT,
    New_Vehicle_ID  INT,
    Old_Driver_ID   INT,
    New_Driver_ID   INT,
    Changed_By      INT NOT NULL,
    Changed_At      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Reason          VARCHAR(255),
    FOREIGN KEY (Rental_ID)      REFERENCES RENTAL(Rental_ID),
    FOREIGN KEY (Old_Vehicle_ID) REFERENCES VEHICLE(Vehicle_ID) ON DELETE SET NULL,
    FOREIGN KEY (New_Vehicle_ID) REFERENCES VEHICLE(Vehicle_ID) ON DELETE SET NULL,
    FOREIGN KEY (Old_Driver_ID)  REFERENCES DRIVER(Driver_ID)   ON DELETE SET NULL,
    FOREIGN KEY (New_Driver_ID)  REFERENCES DRIVER(Driver_ID)   ON DELETE SET NULL,
    FOREIGN KEY (Changed_By)     REFERENCES USER_ACCOUNT(User_ID)
);

-- Loyalty tier trigger: recalculates the customer's tier when a rental is returned
DELIMITER $$
CREATE TRIGGER trg_update_tier AFTER UPDATE ON RENTAL
FOR EACH ROW
BEGIN
  IF OLD.Return_Date IS NULL AND NEW.Return_Date IS NOT NULL THEN
    UPDATE CUSTOMER SET Tier = CASE
      WHEN (SELECT COUNT(*) FROM RENTAL
            WHERE Customer_ID = NEW.Customer_ID AND Return_Date IS NOT NULL) >= 10 THEN 'gold'
      WHEN (SELECT COUNT(*) FROM RENTAL
            WHERE Customer_ID = NEW.Customer_ID AND Return_Date IS NOT NULL) >= 5 THEN 'silver'
      ELSE 'standard' END
    WHERE Customer_ID = NEW.Customer_ID;
  END IF;
END$$
DELIMITER ;
