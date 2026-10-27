-- Car Rental System seed data
-- Load after schema.sql:  mysql -u root -p car_rental < seed.sql
-- Login accounts are created separately by seed_users.py (they need hashed passwords).

USE car_rental;

-- Vehicles. Statuses match the rentals and maintenance rows below.
INSERT INTO VEHICLE (Vehicle_ID, VIN, Plate_Number, Make, Model, Year, Daily_Rate, Status) VALUES
(1, 'JTDBR32E730123456', 'KDA 101A', 'Toyota',     'Corolla', 2023,  3500.00, 'available'),
(2, '1HGCM82633A004352', 'KDB 202B', 'Honda',      'Civic',   2022,  4500.00, 'rented'),
(3, 'WVWZZZ1JZXW000001', 'KDC 303C', 'Volkswagen', 'Golf',    2019,  4000.00, 'available'),
(4, 'MNTAB0AB1JN123456', 'KDD 404D', 'Nissan',     'X-Trail', 2021,  9000.00, 'available'),
(5, 'JTEBU5JR8K5600001', 'KDE 505E', 'Toyota',     'Prado',   2020, 12000.00, 'maintenance');

-- One policy per car.
INSERT INTO INSURANCE_POLICY (Vehicle_ID, Provider, Expiry_Date) VALUES
(1, 'Jubilee Insurance',  '2027-01-15'),
(2, 'Britam',             '2027-03-20'),
(3, 'CIC Insurance',      DATE_ADD(CURDATE(), INTERVAL 20 DAY)),
(4, 'Jubilee Insurance',  '2027-05-05'),
(5, 'APA Insurance',      '2027-08-08');

-- Customers.
INSERT INTO CUSTOMER (Customer_ID, National_ID, First_Name, Last_Name, Email, License_Number, License_Expiry, Tier) VALUES
(1, '12345678', 'Amina', 'Wanjiru', 'amina.wanjiru@example.com', 'DL-2019-001234', '2027-05-01', 'standard'),
(2, '23456789', 'Brian', 'Otieno',  'brian.otieno@example.com',  'DL-2020-005678', '2028-02-10', 'standard'),
(3, '34567890', 'Carol', 'Mutua',   'carol.mutua@example.com',   'DL-2018-009012', '2027-09-15', 'standard');

-- Several phone numbers per customer (keeps CUSTOMER in 1NF).
INSERT INTO CUSTOMER_PHONE (Customer_ID, Phone_Number) VALUES
(1, '+254711000111'),
(1, '+254712000112'),
(2, '+254722000222'),
(3, '+254733000333');

-- Drivers. Driver 1 is on the active rental below, so 'assigned'.
INSERT INTO DRIVER (Driver_ID, First_Name, Last_Name, License_Number, Status) VALUES
(1, 'James', 'Kariuki', 'DL-2017-003344', 'assigned'),
(2, 'Peter', 'Mwangi',  'DL-2019-007788', 'available'),
(3, 'Grace', 'Achieng', 'DL-2021-009900', 'available');

-- Rentals: one returned on time, one active, one returned late.
INSERT INTO RENTAL (Rental_ID, Customer_ID, Vehicle_ID, Driver_ID, Is_Chauffeur, Rental_Date, Due_Date, Return_Date, Total_Cost, Late_Fee) VALUES
(1, 1, 1, NULL, FALSE, DATE_SUB(CURDATE(), INTERVAL 40 DAY), DATE_SUB(CURDATE(), INTERVAL 37 DAY), DATE_SUB(CURDATE(), INTERVAL 37 DAY), 10500.00,     0.00),
(2, 2, 2, 1,    TRUE,  DATE_SUB(CURDATE(), INTERVAL 5 DAY),  DATE_SUB(CURDATE(), INTERVAL 2 DAY),  NULL,                                 22500.00,     0.00),
(3, 3, 3, NULL, FALSE, DATE_SUB(CURDATE(), INTERVAL 20 DAY), DATE_SUB(CURDATE(), INTERVAL 18 DAY), DATE_SUB(CURDATE(), INTERVAL 16 DAY),  8000.00, 12000.00);

-- One service job in progress, which is why vehicle 5 is in maintenance.
INSERT INTO MAINTENANCE (Maintenance_ID, Vehicle_ID, Status, Start_Date, End_Date, Description) VALUES
(1, 5, 'in_progress', DATE_SUB(CURDATE(), INTERVAL 10 DAY), NULL, 'Scheduled full service');
