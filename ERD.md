# Car Rental ER Diagram

Source of truth: `schema.sql`. Open this file on GitHub (or paste the block into
<https://mermaid.live>) to see the diagram.

```mermaid
erDiagram
    CUSTOMER {
        int Customer_ID PK
        varchar National_ID UK
        varchar First_Name
        varchar Last_Name
        varchar Email UK
        varchar License_Number UK
        date License_Expiry
        varchar Tier "standard | silver | gold"
    }
    CUSTOMER_PHONE {
        int Customer_ID PK, FK
        varchar Phone_Number PK
    }
    USER_ACCOUNT {
        int User_ID PK
        varchar Email UK
        varchar Password_Hash
        varchar Role "customer | rental_agent | fleet_manager | driver"
        int Customer_ID UK, FK
        int Driver_ID UK, FK
    }
    DRIVER {
        int Driver_ID PK
        varchar First_Name
        varchar Last_Name
        varchar License_Number UK
        varchar Status "available | assigned"
    }
    VEHICLE {
        int Vehicle_ID PK
        varchar VIN UK
        varchar Plate_Number UK
        varchar Make
        varchar Model
        int Year
        decimal Daily_Rate
        varchar Status "available | rented | maintenance"
    }
    INSURANCE_POLICY {
        int Policy_ID PK
        int Vehicle_ID UK, FK
        varchar Provider
        date Expiry_Date
    }
    RENTAL {
        int Rental_ID PK
        int Customer_ID FK
        int Vehicle_ID FK "NULL if the car is removed"
        int Driver_ID FK "NULL when self-drive"
        boolean Is_Chauffeur
        date Rental_Date
        date Due_Date
        date Return_Date "NULL while open"
        decimal Total_Cost
        decimal Late_Fee
    }
    MAINTENANCE {
        int Maintenance_ID PK
        int Vehicle_ID FK
        varchar Status "scheduled | in_progress | completed"
        date Start_Date
        date End_Date
        varchar Description
    }
    ASSIGNMENT_HISTORY {
        int History_ID PK
        int Rental_ID FK
        int Old_Vehicle_ID FK
        int New_Vehicle_ID FK
        int Old_Driver_ID FK
        int New_Driver_ID FK
        int Changed_By FK "USER_ACCOUNT"
        datetime Changed_At
        varchar Reason
    }

    CUSTOMER ||--o{ CUSTOMER_PHONE : "has"
    CUSTOMER ||--o{ RENTAL : "books"
    CUSTOMER |o--o| USER_ACCOUNT : "logs in as"
    DRIVER |o--o| USER_ACCOUNT : "logs in as"
    DRIVER |o--o{ RENTAL : "chauffeurs"
    VEHICLE |o--o{ RENTAL : "is rented in"
    VEHICLE |o--|| INSURANCE_POLICY : "is covered by"
    VEHICLE ||--o{ MAINTENANCE : "is serviced in"
    RENTAL ||--o{ ASSIGNMENT_HISTORY : "is changed in"
```

## Notes

- **Rental status is derived, never stored.** `returned` when `Return_Date` is set,
  `overdue` when `Due_Date < CURDATE()`, otherwise `active`.
- **One policy per car.** `INSURANCE_POLICY.Vehicle_ID` is `UNIQUE`; saving a policy
  for a car that already has one renews it.
- **Deleting a car keeps history.** `RENTAL.Vehicle_ID` and both vehicle columns in
  `ASSIGNMENT_HISTORY` use `ON DELETE SET NULL`.
- **Tier is automatic.** `trg_update_tier` recalculates `CUSTOMER.Tier` when a rental's
  `Return_Date` goes from `NULL` to a date: 0-4 standard, 5-9 silver, 10+ gold.
- **A login belongs to at most one person.** `USER_ACCOUNT.Customer_ID` and
  `Driver_ID` are both `UNIQUE`; agents and managers have neither.
