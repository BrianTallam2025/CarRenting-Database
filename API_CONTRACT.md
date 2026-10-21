# API_CONTRACT.md

The promise between backend and frontend: for every page, exactly what data the page is
handed and exactly what the form sends back. If a name is not in this file, do not assume it.

Written by B1. Rules: nobody renames a variable without updating this file first and telling
the person it affects. If something is unclear, ask here, do not guess. Add new names freely;
never remove or rename an existing one without agreement.

Template file for each page follows the README tree (`shared/`, `customer/`, `agent/`, `fleet/`, `driver/`).

## Naming rules

- **Object aliases are lowercase:** `vehicle`, `customer`, `driver`, `rental`, `policy`, `job`, `account`, `history`.
- **Fields use the exact database column names:** `vehicle.Make`, `vehicle.Plate_Number`, `vehicle.Daily_Rate`, `customer.Tier`, `rental.Due_Date`.
- **Lists are plural and lowercase:** `vehicles`, `rentals`, `drivers`, `customers`, `policies`, `jobs`, `trips`.
- **Computed values are lowercase snake_case:** `today`, `days`, `days_late`, `late_fee`, `amount_due`, `discount_percent`.
- Every object also carries its primary key: `vehicle.Vehicle_ID`, `customer.Customer_ID`, `driver.Driver_ID`, `rental.Rental_ID`, `policy.Policy_ID`, `job.Maintenance_ID`.

---

## F1: shared, public and driver pages

### Landing
```
Route:        GET /
Who can open: Public
Page gets:    featured_vehicles - list of
              vehicle.Vehicle_ID, vehicle.Make, vehicle.Model, vehicle.Year, vehicle.Daily_Rate
Form sends:   no form
After submit: n/a
Errors:       none
```

### Login
```
Route:        GET /login
Who can open: Public
Page gets:    nothing (form only)
Form sends:   POST /login
              email, password
After submit: redirect by role: customer -> /customer, rental_agent -> /agent,
              fleet_manager -> /fleet, driver -> /driver
Errors:       'Wrong email or password' as a red flash message
```

### Register
```
Route:        GET /register
Who can open: Public
Page gets:    nothing (form only)
Form sends:   POST /register
              first_name, last_name, email, password,
              national_id, license_number, license_expiry
After submit: logs the new customer in and goes to /customer
Errors:       'Email already registered', 'License number already used' as red flash messages
```

### No access (403)
```
Route:        n/a (error handler)
Who can open: Anyone
Page gets:    current_user.role
Form sends:   no form
After submit: n/a
Errors:       none
```

### Error (404 and 500)
```
Route:        n/a (error handler)
Who can open: Anyone
Page gets:    code (404 or 500)
Form sends:   no form
After submit: n/a
Errors:       none
```

### Driver: current assignment
```
Route:        GET /driver
Who can open: Driver
Page gets:    rental.Rental_ID, rental.Rental_Date, rental.Due_Date,
              vehicle.Make, vehicle.Model, vehicle.Plate_Number,
              customer.First_Name, customer.Last_Name, customer_phone,
              upcoming - list of rental.Rental_ID, rental.Rental_Date, rental.Due_Date,
              vehicle.Make, vehicle.Model
Form sends:   no form
After submit: n/a
Errors:       none ('no current assignment' shown when there is no active rental)
```

### Driver: trip history
```
Route:        GET /driver/history
Who can open: Driver
Page gets:    trips - list of
              rental.Rental_ID, rental.Rental_Date, rental.Due_Date, rental.Return_Date,
              vehicle.Make, vehicle.Model, vehicle.Plate_Number
Form sends:   no form
After submit: n/a
Errors:       none
```

---

## F2: customer pages

### Dashboard
```
Route:        GET /customer
Who can open: Customer
Page gets:    customer.Tier,
              active_rental - rental.Rental_ID, rental.Due_Date,
              vehicle.Make, vehicle.Model, vehicle.Plate_Number,
              recent_rentals - list of rental.Rental_ID, rental.Rental_Date, rental.Due_Date,
              vehicle.Make, vehicle.Model
Form sends:   no form
After submit: n/a
Errors:       none
```

### Browse cars
```
Route:        GET /vehicles
Who can open: Customer
Page gets:    vehicles - list of
              vehicle.Vehicle_ID, vehicle.VIN, vehicle.Plate_Number, vehicle.Make,
              vehicle.Model, vehicle.Year, vehicle.Daily_Rate, vehicle.Status
              (only available cars with unexpired insurance)
Filter (URL): ?make=, ?max_price=
Form sends:   GET filter form (make, max_price)
After submit: same page, filtered
Errors:       none
```

### Car details
```
Route:        GET /vehicles/<id>
Who can open: Customer
Page gets:    vehicle.Vehicle_ID, vehicle.VIN, vehicle.Plate_Number, vehicle.Make,
              vehicle.Model, vehicle.Year, vehicle.Daily_Rate, vehicle.Status
Form sends:   no form (Rent button links to /rent/<vehicle_id>)
After submit: n/a
Errors:       'Vehicle not found' as a 404 page
```

### Rent form
```
Route:        GET /rent/<vehicle_id>
Who can open: Customer
Page gets:    vehicle.Vehicle_ID, vehicle.Make, vehicle.Model, vehicle.Daily_Rate,
              customer.Tier, discount_percent
Form sends:   POST /rent/<vehicle_id>
              start_date, end_date, is_chauffeur (true or false)
After submit: goes to /rentals/<rental_id>/confirmation
Errors:       'Your driving license has expired', 'Vehicle not available' as red flash messages
```

### Confirmation
```
Route:        GET /rentals/<id>/confirmation
Who can open: Customer (own rental only)
Page gets:    rental.Rental_ID, rental.Rental_Date, rental.Due_Date, rental.Total_Cost,
              rental.Is_Chauffeur, rental.Late_Fee,
              vehicle.Make, vehicle.Model, vehicle.Plate_Number,
              driver.First_Name, driver.Last_Name (empty when self-drive)
Form sends:   no form
After submit: n/a
Errors:       'Rental not found' as a 404 page
```

### My rentals
```
Route:        GET /my-rentals
Who can open: Customer
Page gets:    rentals - list of
              rental.Rental_ID, rental.Rental_Date, rental.Due_Date, rental.Return_Date,
              rental.Total_Cost, rental.Late_Fee, amount_due,
              vehicle.Make, vehicle.Model
Form sends:   no form
After submit: n/a
Errors:       none
```

### My profile
```
Route:        GET /profile
Who can open: Customer
Page gets:    customer.First_Name, customer.Last_Name, customer.Email, customer.National_ID,
              customer.License_Number, customer.License_Expiry, customer.Tier,
              phones - list of customer_phone.Phone_Number
Form sends:   POST /profile
              phones (list of phone numbers)
After submit: saves and returns to /profile
Errors:       'Phone number must be unique for you', success shown as a green flash message
```

---

## F3: rental agent pages and the two reassign pages

### Agent dashboard
```
Route:        GET /agent
Who can open: Rental Agent
Page gets:    due_today - list of rental.Rental_ID, rental.Due_Date,
              customer.First_Name, customer.Last_Name, vehicle.Plate_Number,
              overdue - list of rental.Rental_ID, rental.Due_Date,
              customer.First_Name, customer.Last_Name, vehicle.Plate_Number,
              days_late (per row)
Form sends:   no form
After submit: n/a
Errors:       none
```

### All rentals
```
Route:        GET /agent/rentals
Who can open: Rental Agent
Page gets:    rentals - list of
              rental.Rental_ID, rental.Rental_Date, rental.Due_Date, rental.Return_Date,
              customer.First_Name, customer.Last_Name,
              vehicle.Make, vehicle.Model, vehicle.Plate_Number,
              driver.First_Name, driver.Last_Name (empty when self-drive)
Filter (URL): ?search= (name, plate or rental id)
Form sends:   GET filter form (search)
After submit: same page, filtered
Errors:       none
```

### Rental details
```
Route:        GET /agent/rentals/<id>
Who can open: Rental Agent
Page gets:    rental.Rental_ID, rental.Rental_Date, rental.Due_Date, rental.Return_Date,
              rental.Is_Chauffeur, rental.Total_Cost, rental.Late_Fee, amount_due,
              customer.First_Name, customer.Last_Name, customer.Email, customer.Tier,
              vehicle.Make, vehicle.Model, vehicle.Plate_Number, vehicle.Daily_Rate,
              driver.First_Name, driver.Last_Name (empty when self-drive)
Form sends:   no form (links to return and assign-driver)
After submit: n/a
Errors:       'Rental not found' as a 404 page
```

### Walk-in rental
```
Route:        GET /agent/rent
Who can open: Rental Agent
Page gets:    customers - list of customer.Customer_ID, customer.First_Name,
              customer.Last_Name, customer.Email, customer.Tier,
              vehicles - list of vehicle.Vehicle_ID, vehicle.Make, vehicle.Model,
              vehicle.Plate_Number, vehicle.Daily_Rate (available only),
              drivers - list of driver.Driver_ID, driver.First_Name, driver.Last_Name (free only)
Form sends:   POST /agent/rent
              customer_id (existing) OR new_customer fields (first_name, last_name, email,
              national_id, license_number, license_expiry),
              vehicle_id, start_date, end_date, is_chauffeur, driver_id (optional)
After submit: goes to /agent/rentals/<rental_id>
Errors:       'Vehicle not available', 'Customer license expired', 'Driver not available'
```

### Process return
```
Route:        GET /agent/rentals/<id>/return
Who can open: Rental Agent
Page gets:    rental.Rental_ID, rental.Rental_Date, rental.Due_Date, rental.Total_Cost,
              vehicle.Make, vehicle.Model, vehicle.Daily_Rate,
              customer.First_Name, customer.Last_Name,
              today
Form sends:   POST /agent/rentals/<id>/return
              return_date
After submit: goes to /agent/rentals/<id>
Errors:       'Rental already returned' as a red flash message
```

### Assign driver
```
Route:        GET /agent/rentals/<id>/assign-driver
Who can open: Rental Agent
Page gets:    rental.Rental_ID, rental.Is_Chauffeur,
              free_drivers - list of driver.Driver_ID, driver.First_Name, driver.Last_Name
Form sends:   POST /agent/rentals/<id>/assign-driver
              driver_id
After submit: goes to /agent/rentals/<id>
Errors:       'Driver is not available' as a red flash message
```

### Customer lookup
```
Route:        GET /agent/customers
Who can open: Rental Agent
Page gets:    customers - list of customer.Customer_ID, customer.First_Name,
              customer.Last_Name, customer.Email, customer.Tier,
              selected - customer.First_Name, customer.Last_Name, customer.Tier,
              rentals - list of rental.Rental_ID, rental.Rental_Date, rental.Due_Date,
              vehicle.Make, vehicle.Model (for the selected customer)
Filter (URL): ?q= (name, email or license number)
Form sends:   GET search form (q)
After submit: same page, filtered
Errors:       none
```

### Change car or driver (reassign)
```
Route:        GET /fleet/rentals/<id>/reassign
Who can open: Fleet Manager
Page gets:    rental.Rental_ID, rental.Rental_Date, rental.Due_Date,
              vehicle.Make, vehicle.Model, vehicle.Plate_Number (current),
              driver.First_Name, driver.Last_Name (current, empty when self-drive),
              available_vehicles - list of vehicle.Vehicle_ID, vehicle.Make, vehicle.Model,
              vehicle.Plate_Number, vehicle.Daily_Rate (available and insured),
              free_drivers - list of driver.Driver_ID, driver.First_Name, driver.Last_Name
Form sends:   POST /fleet/rentals/<id>/reassign
              vehicle_id, driver_id, reason
After submit: goes to /fleet/assignment-history
Errors:       'Vehicle not insured', 'Vehicle not available', 'Driver not available'
```

### Assignment history
```
Route:        GET /fleet/assignment-history
Who can open: Fleet Manager
Page gets:    history - list of
              history.History_ID, history.Rental_ID, history.Changed_At, history.Reason,
              history.Old_Vehicle_ID, history.New_Vehicle_ID,
              history.Old_Driver_ID, history.New_Driver_ID,
              changed_by (email of the user who made the change)
Form sends:   no form
After submit: n/a
Errors:       none
```

---

## F4: fleet manager pages

### Fleet dashboard
```
Route:        GET /fleet
Who can open: Fleet Manager
Page gets:    counts - available, rented, maintenance (integers),
              expiring_policies - list of policy.Policy_ID, policy.Expiry_Date,
              vehicle.Make, vehicle.Model, vehicle.Plate_Number
Form sends:   no form
After submit: n/a
Errors:       none
```

### Car list
```
Route:        GET /fleet/vehicles
Who can open: Fleet Manager
Page gets:    vehicles - list of
              vehicle.Vehicle_ID, vehicle.VIN, vehicle.Plate_Number, vehicle.Make,
              vehicle.Model, vehicle.Year, vehicle.Daily_Rate, vehicle.Status
Form sends:   no form (links to add and edit)
After submit: n/a
Errors:       none
```

### Add car / Edit car
```
Route:        GET /fleet/vehicles/new
              GET /fleet/vehicles/<id>/edit
Who can open: Fleet Manager
Page gets:    vehicle.* on edit (empty on add):
              vehicle.Vehicle_ID, vehicle.VIN, vehicle.Plate_Number, vehicle.Make,
              vehicle.Model, vehicle.Year, vehicle.Daily_Rate, vehicle.Status
Form sends:   POST /fleet/vehicles/new
              POST /fleet/vehicles/<id>/edit
              vin, plate_number, make, model, year, daily_rate, status
After submit: goes to /fleet/vehicles
Errors:       'VIN already exists', 'Plate number already exists' as red flash messages
```

### Insurance
```
Route:        GET /fleet/insurance
Who can open: Fleet Manager
Page gets:    policies - list of
              policy.Policy_ID, policy.Provider, policy.Expiry_Date,
              vehicle.Make, vehicle.Model, vehicle.Plate_Number,
              vehicles - list of vehicle.Vehicle_ID, vehicle.Make, vehicle.Model,
              vehicle.Plate_Number (for adding a policy)
Form sends:   POST /fleet/insurance
              vehicle_id, provider, expiry_date
After submit: saves and returns to /fleet/insurance
Errors:       'This car already has a policy' as a red flash message
```

### Maintenance list
```
Route:        GET /fleet/maintenance
Who can open: Fleet Manager
Page gets:    jobs - list of
              job.Maintenance_ID, job.Status, job.Start_Date, job.End_Date, job.Description,
              vehicle.Make, vehicle.Model, vehicle.Plate_Number
Form sends:   no form (links to schedule; how a job is marked complete is still open - see below)
After submit: n/a
Errors:       none
```

### Schedule maintenance
```
Route:        GET /fleet/maintenance/new
Who can open: Fleet Manager
Page gets:    vehicles - list of vehicle.Vehicle_ID, vehicle.Make, vehicle.Model,
              vehicle.Plate_Number, vehicle.Status (not currently rented)
Form sends:   POST /fleet/maintenance/new
              vehicle_id, start_date, description
After submit: goes to /fleet/maintenance
Errors:       'This car is already scheduled for maintenance',
              'A rented car cannot go into maintenance'
```

### Driver list
```
Route:        GET /fleet/drivers
Who can open: Fleet Manager
Page gets:    drivers - list of
              driver.Driver_ID, driver.First_Name, driver.Last_Name,
              driver.License_Number, driver.Status
Form sends:   no form (links to add and edit)
After submit: n/a
Errors:       none
```

### Add or edit driver
```
Route:        GET /fleet/drivers/new
              GET /fleet/drivers/<id>/edit
Who can open: Fleet Manager
Page gets:    driver.* on edit (empty on add):
              driver.Driver_ID, driver.First_Name, driver.Last_Name,
              driver.License_Number, driver.Status
Form sends:   POST /fleet/drivers/new
              POST /fleet/drivers/<id>/edit
              first_name, last_name, license_number, status
After submit: goes to /fleet/drivers
Errors:       'License number already exists' as a red flash message
```

---

## Open questions (ask here, do not guess)

- Status values: rentals use `active`, `completed`, `cancelled`? The schema has no Status column
  on RENTAL (it derives state from `Return_Date`). Decide before B2 builds the rental lists.
- Maintenance status change: a dedicated POST route, or an edit form? Not yet fixed above.
