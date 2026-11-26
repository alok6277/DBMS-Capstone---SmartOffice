# SmartOffice – Enhanced Workspace Allocation System

## Latest upgrade
- Live dashboard desk availability: available vs currently occupied desks.
- Interactive office floor map at `/floor-map` with date selection.
- Green tiles indicate available resources, red tiles indicate reserved/occupied resources, and purple tiles indicate meeting rooms.
- Floor map is accessible from the left navigation and dashboard quick actions.
- Desk/room status is calculated from active bookings in SQLite.

## Preserve your existing database when updating
This source ZIP intentionally does not include a database snapshot. Before running this upgraded version, copy your existing `smart_office.db` from your current working project folder into this `smart-office-system` folder if you want to keep your employees and booking history. If you do not copy it, the application creates a fresh demo database from `schema.sql` on first start.

## Run locally (Windows PowerShell)
```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py app.py
```
Open http://127.0.0.1:5000

Demo accounts (fresh database):
- Admin: admin@smartoffice.local / Admin@123
- Facility Manager: facility@smartoffice.local / Facility@123
- Employee: aarav@smartoffice.local / Employee@123

## Notes
- SQLite is the primary database.
- MongoDB extension is optional and has separate requirements in `requirements-mongodb.txt`.
- Change `SECRET_KEY` before production deployment.
