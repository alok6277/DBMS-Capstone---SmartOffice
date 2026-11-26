PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS employee (
 employee_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('EMPLOYEE','FACILITY_MANAGER','ADMIN')),
 department TEXT, status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','INACTIVE')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS office (office_id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,address TEXT);
CREATE TABLE IF NOT EXISTS floor (floor_id INTEGER PRIMARY KEY AUTOINCREMENT,office_id INTEGER NOT NULL REFERENCES office(office_id),name TEXT NOT NULL,floor_number INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS zone (zone_id INTEGER PRIMARY KEY AUTOINCREMENT,floor_id INTEGER NOT NULL REFERENCES floor(floor_id),name TEXT NOT NULL,description TEXT);
CREATE TABLE IF NOT EXISTS desk (desk_id INTEGER PRIMARY KEY AUTOINCREMENT,zone_id INTEGER NOT NULL REFERENCES zone(zone_id),desk_code TEXT NOT NULL UNIQUE,capacity INTEGER NOT NULL DEFAULT 1 CHECK(capacity>0),status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE TABLE IF NOT EXISTS room (room_id INTEGER PRIMARY KEY AUTOINCREMENT,zone_id INTEGER NOT NULL REFERENCES zone(zone_id),room_code TEXT NOT NULL UNIQUE,capacity INTEGER NOT NULL CHECK(capacity>0),status TEXT NOT NULL DEFAULT 'ACTIVE');
CREATE TABLE IF NOT EXISTS amenity (amenity_id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE,description TEXT);
CREATE TABLE IF NOT EXISTS resource_amenity (resource_amenity_id INTEGER PRIMARY KEY AUTOINCREMENT,resource_type TEXT NOT NULL CHECK(resource_type IN ('DESK','ROOM')),resource_id INTEGER NOT NULL,amenity_id INTEGER NOT NULL REFERENCES amenity(amenity_id),UNIQUE(resource_type,resource_id,amenity_id));
CREATE TABLE IF NOT EXISTS booking (
 booking_id INTEGER PRIMARY KEY AUTOINCREMENT,employee_id INTEGER NOT NULL REFERENCES employee(employee_id),
 resource_type TEXT NOT NULL CHECK(resource_type IN ('DESK','ROOM')),resource_id INTEGER NOT NULL,
 booking_date TEXT NOT NULL,start_time TEXT NOT NULL,end_time TEXT NOT NULL,purpose TEXT,attendees INTEGER NOT NULL DEFAULT 1 CHECK(attendees>0),
 status TEXT NOT NULL DEFAULT 'CONFIRMED' CHECK(status IN ('CONFIRMED','CHECKED_IN','COMPLETED','CANCELLED')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK(start_time < end_time)
);
CREATE INDEX IF NOT EXISTS idx_booking_resource_time ON booking(resource_type,resource_id,booking_date,start_time,end_time,status);
CREATE INDEX IF NOT EXISTS idx_booking_employee ON booking(employee_id,booking_date);
CREATE TABLE IF NOT EXISTS cancellation (cancellation_id INTEGER PRIMARY KEY AUTOINCREMENT,booking_id INTEGER NOT NULL UNIQUE REFERENCES booking(booking_id),cancelled_by INTEGER NOT NULL REFERENCES employee(employee_id),reason TEXT,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS access_log (log_id INTEGER PRIMARY KEY AUTOINCREMENT,employee_id INTEGER NOT NULL REFERENCES employee(employee_id),action TEXT NOT NULL,details TEXT,ip_address TEXT,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE VIEW IF NOT EXISTS current_availability AS
 SELECT 'DESK' resource_type,d.desk_id resource_id,d.desk_code resource_code,d.capacity,d.status FROM desk d
 UNION ALL SELECT 'ROOM',r.room_id,r.room_code,r.capacity,r.status FROM room r;
