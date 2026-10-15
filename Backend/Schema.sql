
--  Lab 5 & 6: Car Rental System

CREATE SCHEMA IF NOT EXISTS car_rental;
USE car_rental;

-- Table 1: CarCategories
CREATE TABLE CarCategories (
    CategoryID INT NOT NULL,
    CategoryName VARCHAR(50) NOT NULL,
    PRIMARY KEY (CategoryID)
);

-- Table 2: Customers
CREATE TABLE Customers (
    CustomerID INT NOT NULL,
    FullName VARCHAR(100) NOT NULL,
    ContactPhone VARCHAR(20) NOT NULL,
    DrivingLicenceNo VARCHAR(30) NOT NULL,
    PRIMARY KEY (CustomerID),
    UNIQUE INDEX DrivingLicenceNo_UNIQUE (DrivingLicenceNo ASC) VISIBLE );

-- Table 3: Cars (references CarCategories)
CREATE TABLE Cars (
    CarID INT NOT NULL,
    Make VARCHAR(50) NOT NULL,
    Model VARCHAR(50) NOT NULL,
    RegNumber VARCHAR(20) NOT NULL,
    DailyRate DECIMAL(10, 2) NOT NULL,   -- KES per day
    CategoryID INT NOT NULL,
    PRIMARY KEY (CarID),
    UNIQUE INDEX RegNumber_UNIQUE (RegNumber ASC),
    CONSTRAINT FK_Cars_Categories FOREIGN KEY (CategoryID) REFERENCES CarCategories (CategoryID)
);

-- Table 4: Rentals (references Cars and Customers)

CREATE TABLE Rentals (
    RentalID INT NOT NULL,
    CarID INT NOT NULL,
    CustomerID INT NOT NULL,
    StartDate DATE NOT NULL,
    EndDate DATE NOT NULL,
    PRIMARY KEY (RentalID),
    CONSTRAINT FK_Rentals_Cars FOREIGN KEY (CarID) REFERENCES Cars (CarID),
    CONSTRAINT FK_Rentals_Customers FOREIGN KEY (CustomerID) REFERENCES Customers (CustomerID)
);

USE car_rental;

INSERT INTO CarCategories (CategoryID, CategoryName) VALUES
(101, 'Economy'),
(102, 'SUV'),
(103, 'Van'),
(104, 'Luxury');

INSERT INTO Customers (CustomerID, FullName, ContactPhone, DrivingLicenceNo) VALUES
(1, 'Amina Wanjiru', '+254711000111', 'DL-2019-001234'),
(2, 'Brian Otieno', '+254722000222', 'DL-2020-005678'),
(3, 'Carol Mutua', '+254733000333', 'DL-2018-009012');

INSERT INTO Cars (CarID, Make, Model, RegNumber, DailyRate, CategoryID) VALUES
(501, 'Mazda', 'Demio', 'KDA 101A', 3500.00, 101),
(502, 'Toyota', 'Vitz', 'KDB 202B', 3200.00, 101),
(503, 'Toyota', 'Prado', 'KDC 303C', 12000.00, 102),
(504, 'Nissan', 'X-Trail', 'KDD 404D', 9000.00, 102),
(505, 'Toyota', 'Hiace', 'KDE 505E', 10000.00, 103),
(506, 'Mercedes-Benz', 'E-Class', 'KDF 606F', 20000.00, 104);

INSERT INTO Rentals (RentalID, CarID, CustomerID, StartDate, EndDate) VALUES
(1001, 501, 1, '2026-03-01', '2026-03-04'),
(1002, 503, 2, '2026-03-02', '2026-03-07'),
(1003, 505, 3, '2026-03-05', '2026-03-06'),
(1004, 501, 2, '2026-03-10', '2026-03-12'),
(1005, 506, 1, '2026-03-15', '2026-03-18'),
(1006, 502, 3, '2026-03-20', '2026-03-25');

SELECT * FROM car_rental.CarCategories;

SELECT * FROM car_rental.Customers;

SELECT
    c.CarID,
    c.Make,
    c.Model,
    c.RegNumber,
    c.DailyRate,
    cc.CategoryName
FROM car_rental.Cars c
JOIN car_rental.CarCategories cc ON c.CategoryID = cc.CategoryID;

SELECT
    r.RentalID,
    cu.FullName,
    c.Make,
    c.Model,
    c.RegNumber,
    r.StartDate,
    r.EndDate,
    DATEDIFF(r.EndDate, r.StartDate) AS DaysRented,
    DATEDIFF(r.EndDate, r.StartDate) * c.DailyRate AS TotalCost
FROM car_rental.Rentals r
JOIN car_rental.Cars c ON r.CarID = c.CarID
JOIN car_rental.Customers cu ON r.CustomerID = cu.CustomerID;
