# DriveDesk — F3 Rental Agent Pages

## Files
- `rental_agent_pages.html`: responsive front-end prototype with all F3 screens.
- `rental_database_schema.sql`: suggested MySQL/MariaDB relational schema for integration.

## Run the interface
1. Extract the ZIP file.
2. Open `rental_agent_pages.html` in a modern browser.
3. Use the left menu to navigate between screens.
4. Use the role selector at the top to demonstrate Agent and Manager views.
5. Sample records are included so the pages are populated immediately.

## Screens included
Agent dashboard; all rentals with search/status filter; rental details; walk-in rental; vehicle return with days late, late fee and total; driver assignment; customer lookup; manager-only vehicle/driver change; change history.

## Important project limitation
This is a front-end prototype. Its sample data and edits live in JavaScript memory and reset when the page is refreshed. It is not connected to a live database. The SQL file provides a starting schema; a backend (for example, PHP, Python/Flask, Node.js or Java) must connect the UI to the database. Authentication, role authorization, availability checks and financial calculations must be enforced server-side for a real deployment.
