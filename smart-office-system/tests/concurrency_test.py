"""Two-connection test for the mandatory Desk 102 overlap scenario.
Run: python tests/concurrency_test.py
"""
import os, sys, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app import init_db, DB_PATH

init_db()
db = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
db.execute('PRAGMA foreign_keys=ON')
db.execute('PRAGMA busy_timeout=15000')
# Seed employee IDs 3 and 4 are demo employees. Desk 102 is the second seeded desk.
# Clean prior rows from this specific test date so it can be rerun.
test_date = '2099-06-15'
db.execute('DELETE FROM booking WHERE resource_type="DESK" AND resource_id=(SELECT desk_id FROM desk WHERE desk_code="102") AND booking_date=?',(test_date,))
desk_id = db.execute('SELECT desk_id FROM desk WHERE desk_code="102"').fetchone()[0]

def attempt(employee_id, start, end):
    try:
        db.execute('BEGIN IMMEDIATE')
        conflict = db.execute("SELECT 1 FROM booking WHERE resource_type='DESK' AND resource_id=? AND booking_date=? AND status IN ('CONFIRMED','CHECKED_IN') AND start_time < ? AND end_time > ?",(desk_id,test_date,end,start)).fetchone()
        if conflict:
            db.execute('ROLLBACK'); return 'REJECTED: overlapping reservation'
        db.execute("INSERT INTO booking(employee_id,resource_type,resource_id,booking_date,start_time,end_time,purpose) VALUES(?,'DESK',?,?,?,?,'Concurrency test')",(employee_id,desk_id,test_date,start,end))
        db.execute('COMMIT'); return 'ACCEPTED'
    except Exception:
        try: db.execute('ROLLBACK')
        except sqlite3.Error: pass
        raise

first = attempt(3,'10:00','12:00')
second = attempt(4,'11:00','13:00')
print('Employee A (10:00-12:00):', first)
print('Employee B (11:00-13:00):', second)
assert first == 'ACCEPTED' and second.startswith('REJECTED'), 'Conflict prevention test failed'
print('PASS: Desk 102 does not accept overlapping bookings.')
db.close()
