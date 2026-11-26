import os, sqlite3, hashlib, secrets
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, 'smart_office.db')
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret-key-before-production')
app.config['DATABASE'] = DB_PATH


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'], timeout=15, isolation_level=None)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
        g.db.execute('PRAGMA journal_mode = WAL')
        g.db.execute('PRAGMA busy_timeout = 15000')
    return g.db

@app.teardown_appcontext
def close_db(error=None):
    db = g.pop('db', None)
    if db is not None: db.close()


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 180000).hex()
    return f'{salt}${digest}'


def verify_password(password, stored):
    try:
        salt, digest = stored.split('$', 1)
        return secrets.compare_digest(hash_password(password, salt).split('$', 1)[1], digest)
    except Exception: return False


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute('PRAGMA foreign_keys = ON')
    db.executescript(open(os.path.join(BASE, 'schema.sql'), encoding='utf-8').read())
    count = db.execute('SELECT COUNT(*) FROM employee').fetchone()[0]
    if count == 0:
        users = [
            ('Admin User','admin@smartoffice.local','Admin@123','ADMIN','IT'),
            ('Facility Manager','facility@smartoffice.local','Facility@123','FACILITY_MANAGER','Operations'),
            ('Aarav Sharma','aarav@smartoffice.local','Employee@123','EMPLOYEE','Engineering'),
            ('Priya Verma','priya@smartoffice.local','Employee@123','EMPLOYEE','Design'),
            ('Kabir Singh','kabir@smartoffice.local','Employee@123','EMPLOYEE','Marketing'),
        ]
        for name,email,pw,role,dept in users:
            db.execute('INSERT INTO employee(name,email,password_hash,role,department) VALUES(?,?,?,?,?)',
                       (name,email,hash_password(pw),role,dept))
        db.execute("INSERT INTO office(name,address) VALUES('Smart Office HQ','Gurugram, Haryana')")
        db.execute("INSERT INTO floor(office_id,name,floor_number) VALUES(1,'First Floor',1)")
        db.execute("INSERT INTO floor(office_id,name,floor_number) VALUES(1,'Second Floor',2)")
        db.execute("INSERT INTO zone(floor_id,name,description) VALUES(1,'Quiet Zone','Low-noise individual work area')")
        db.execute("INSERT INTO zone(floor_id,name,description) VALUES(1,'Collaboration Zone','Team work and discussion area')")
        db.execute("INSERT INTO zone(floor_id,name,description) VALUES(2,'Meeting Zone','Rooms for meetings')")
        for i in range(101,109):
            db.execute('INSERT INTO desk(zone_id,desk_code,capacity,status) VALUES(1,?,?,?)',(str(i),1,'ACTIVE'))
        for i in range(201,205):
            db.execute('INSERT INTO desk(zone_id,desk_code,capacity,status) VALUES(2,?,?,?)',(str(i),2,'ACTIVE'))
        db.execute("INSERT INTO room(zone_id,room_code,capacity,status) VALUES(3,'MR-01',8,'ACTIVE')")
        db.execute("INSERT INTO room(zone_id,room_code,capacity,status) VALUES(3,'MR-02',12,'ACTIVE')")
        db.execute("INSERT INTO room(zone_id,room_code,capacity,status) VALUES(3,'MR-03',24,'ACTIVE')")
        for amenity in ['Wi-Fi','Projector','Whiteboard','Coffee Machine','Printer','Video Conferencing']:
            db.execute('INSERT INTO amenity(name,description) VALUES(?,?)',(amenity,amenity+' facility'))
        for rid in (1,2):
            for aid in (1,2,3,4,5,6): db.execute('INSERT INTO resource_amenity(resource_type,resource_id,amenity_id) VALUES(?,?,?)',('ROOM',rid,aid))
        for did in range(1,13):
            for aid in (1,4,5): db.execute('INSERT INTO resource_amenity(resource_type,resource_id,amenity_id) VALUES(?,?,?)',('DESK',did,aid))
    db.commit(); db.close()


def log_action(action, details=''):
    if session.get('user_id'):
        get_db().execute('INSERT INTO access_log(employee_id,action,details,ip_address) VALUES(?,?,?,?)',
                         (session['user_id'], action, details, request.remote_addr))


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please sign in to continue.', 'warning'); return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper


def roles_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if session.get('role') not in roles:
                flash('You do not have permission to access that page.', 'danger'); return redirect(url_for('dashboard'))
            return fn(*args, **kwargs)
        return wrapper
    return deco

@app.context_processor
def inject_globals():
    return {'current_year': datetime.now().year}

@app.route('/')
def index(): return redirect(url_for('dashboard') if session.get('user_id') else url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        user=get_db().execute('SELECT * FROM employee WHERE lower(email)=?',(email,)).fetchone()
        if user and user['status']=='ACTIVE' and verify_password(password,user['password_hash']):
            session.clear(); session['user_id']=user['employee_id']; session['name']=user['name']; session['role']=user['role']
            log_action('LOGIN','Successful sign-in'); return redirect(url_for('dashboard'))
        flash('Invalid email or password.','danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    log_action('LOGOUT','Signed out'); session.clear(); return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    db=get_db()
    active_desks=db.execute("SELECT COUNT(*) FROM desk WHERE status='ACTIVE'").fetchone()[0]
    occupied_desks=db.execute("""SELECT COUNT(DISTINCT d.desk_id) FROM desk d JOIN booking b
      ON b.resource_type='DESK' AND b.resource_id=d.desk_id
      WHERE d.status='ACTIVE' AND b.booking_date=date('now','localtime')
      AND b.status IN ('CONFIRMED','CHECKED_IN')
      AND b.start_time <= time('now','localtime') AND b.end_time > time('now','localtime')""").fetchone()[0]
    stats={
      'employees':db.execute("SELECT COUNT(*) FROM employee WHERE status='ACTIVE'").fetchone()[0],
      'desks':active_desks,
      'available_desks':max(active_desks-occupied_desks,0),
      'occupied_desks':occupied_desks,
      'rooms':db.execute("SELECT COUNT(*) FROM room WHERE status='ACTIVE'").fetchone()[0],
      'bookings':db.execute("SELECT COUNT(*) FROM booking WHERE status IN ('CONFIRMED','CHECKED_IN','COMPLETED') AND booking_date=date('now','localtime')").fetchone()[0],
      'checkins':db.execute("SELECT COUNT(*) FROM booking WHERE status='CHECKED_IN' AND booking_date=date('now','localtime')").fetchone()[0]
    }
    recent=db.execute('''SELECT b.*,e.name employee_name, CASE WHEN b.resource_type='DESK' THEN d.desk_code ELSE r.room_code END resource_code
       FROM booking b JOIN employee e ON e.employee_id=b.employee_id
       LEFT JOIN desk d ON b.resource_type='DESK' AND d.desk_id=b.resource_id
       LEFT JOIN room r ON b.resource_type='ROOM' AND r.room_id=b.resource_id
       ORDER BY b.created_at DESC LIMIT 8''').fetchall()
    return render_template('dashboard.html',stats=stats,recent=recent)

@app.route('/bookings')
@login_required
def bookings():
    rows=get_db().execute('''SELECT b.*, e.name employee_name,
      CASE WHEN b.resource_type='DESK' THEN d.desk_code ELSE r.room_code END resource_code
      FROM booking b JOIN employee e ON e.employee_id=b.employee_id
      LEFT JOIN desk d ON b.resource_type='DESK' AND d.desk_id=b.resource_id
      LEFT JOIN room r ON b.resource_type='ROOM' AND r.room_id=b.resource_id
      WHERE (?='ADMIN' OR ?='FACILITY_MANAGER' OR b.employee_id=?) ORDER BY b.booking_date DESC,b.start_time DESC''',
      (session['role'],session['role'],session['user_id'])).fetchall()
    return render_template('bookings.html',bookings=rows)

@app.route('/book', methods=['GET','POST'])
@login_required
def book():
    db=get_db()
    if request.method=='POST':
        typ=request.form.get('resource_type','DESK'); rid=request.form.get('resource_id',type=int)
        bdate=request.form.get('booking_date',''); start=request.form.get('start_time',''); end=request.form.get('end_time','')
        purpose=request.form.get('purpose','').strip(); attendees=request.form.get('attendees',1,type=int)
        try:
            datetime.strptime(bdate,'%Y-%m-%d'); datetime.strptime(start,'%H:%M'); datetime.strptime(end,'%H:%M')
            if typ not in ('DESK','ROOM') or not rid or not start < end: raise ValueError()
        except ValueError:
            flash('Please enter valid resource, date and time (end time must be after start time).','danger'); return redirect(url_for('book'))
        if bdate < date.today().isoformat(): flash('Past dates cannot be booked.','danger'); return redirect(url_for('book'))
        try:
            # IMMEDIATE transaction serializes competing writers before overlap validation.
            db.execute('BEGIN IMMEDIATE')
            resource=db.execute('SELECT capacity,status FROM '+('desk' if typ=='DESK' else 'room')+' WHERE '+('desk_id' if typ=='DESK' else 'room_id')+'=?',(rid,)).fetchone()
            if not resource or resource['status']!='ACTIVE': raise Exception('Selected resource is not available.')
            if typ=='ROOM' and attendees>resource['capacity']: raise Exception('Attendees exceed the room capacity.')
            conflict=db.execute('''SELECT booking_id FROM booking WHERE resource_type=? AND resource_id=? AND booking_date=?
              AND status IN ('CONFIRMED','CHECKED_IN') AND start_time < ? AND end_time > ? LIMIT 1''',
              (typ,rid,bdate,end,start)).fetchone()
            if conflict: raise Exception('Booking conflict: this resource is already reserved for an overlapping time interval.')
            cur=db.execute('''INSERT INTO booking(employee_id,resource_type,resource_id,booking_date,start_time,end_time,purpose,attendees,status)
              VALUES(?,?,?,?,?,?,?,?, 'CONFIRMED')''',(session['user_id'],typ,rid,bdate,start,end,purpose,attendees))
            db.execute('INSERT INTO access_log(employee_id,action,details,ip_address) VALUES(?,?,?,?)',(session['user_id'],'BOOKING_CREATED',f'{typ} #{rid}, {bdate} {start}-{end}',request.remote_addr))
            db.execute('COMMIT'); flash('Booking created successfully.','success'); return redirect(url_for('bookings'))
        except Exception as ex:
            try: db.execute('ROLLBACK')
            except sqlite3.Error: pass
            flash(str(ex),'danger'); return redirect(url_for('book'))
    desks=db.execute("SELECT d.desk_id,d.desk_code,d.capacity,z.name zone_name,f.name floor_name FROM desk d JOIN zone z ON z.zone_id=d.zone_id JOIN floor f ON f.floor_id=z.floor_id WHERE d.status='ACTIVE'").fetchall()
    rooms=db.execute("SELECT r.room_id,r.room_code,r.capacity,z.name zone_name FROM room r JOIN zone z ON z.zone_id=r.zone_id WHERE r.status='ACTIVE'").fetchall()
    return render_template('book.html',desks=desks,rooms=rooms,today=date.today().isoformat())

@app.route('/booking/<int:booking_id>/<action>',methods=['POST'])
@login_required
def booking_action(booking_id,action):
    db=get_db(); row=db.execute('SELECT * FROM booking WHERE booking_id=?',(booking_id,)).fetchone()
    if not row: flash('Booking not found.','danger'); return redirect(url_for('bookings'))
    if session['role'] not in ('ADMIN','FACILITY_MANAGER') and row['employee_id']!=session['user_id']:
        flash('You cannot modify another employee booking.','danger'); return redirect(url_for('bookings'))
    if action=='cancel' and row['status']=='CONFIRMED': new='CANCELLED'
    elif action=='checkin' and row['status']=='CONFIRMED': new='CHECKED_IN'
    elif action=='checkout' and row['status']=='CHECKED_IN': new='COMPLETED'
    else: flash('This action is not valid for the current booking status.','warning'); return redirect(url_for('bookings'))
    db.execute('UPDATE booking SET status=?,updated_at=CURRENT_TIMESTAMP WHERE booking_id=?',(new,booking_id))
    if new=='CANCELLED': db.execute('INSERT INTO cancellation(booking_id,cancelled_by,reason) VALUES(?,?,?)',(booking_id,session['user_id'],'Cancelled by user or facility manager'))
    log_action('BOOKING_'+new,f'Booking #{booking_id}'); flash(f'Booking {new.lower().replace("_"," ")} successfully.','success')
    return redirect(url_for('bookings'))

@app.route('/floor-map')
@login_required
def floor_map():
    db=get_db()
    selected_date=request.args.get('date') or date.today().isoformat()
    try:
        datetime.strptime(selected_date,'%Y-%m-%d')
    except ValueError:
        selected_date=date.today().isoformat()
    now_time=datetime.now().strftime('%H:%M')
    desks=db.execute('''SELECT d.desk_id resource_id,d.desk_code resource_code,d.capacity,d.status,
        z.name zone_name,f.name floor_name,
        b.start_time,b.end_time,e.name employee_name
        FROM desk d JOIN zone z ON z.zone_id=d.zone_id JOIN floor f ON f.floor_id=z.floor_id
        LEFT JOIN booking b ON b.booking_id=(SELECT b2.booking_id FROM booking b2
          WHERE b2.resource_type='DESK' AND b2.resource_id=d.desk_id
          AND b2.booking_date=? AND b2.status IN ('CONFIRMED','CHECKED_IN')
          AND ((?=? AND b2.start_time<=? AND b2.end_time>?) OR (?<>?))
          ORDER BY b2.start_time LIMIT 1)
        LEFT JOIN employee e ON e.employee_id=b.employee_id
        ORDER BY f.floor_number,z.name,d.desk_code''',
        (selected_date,date.today().isoformat(),selected_date,now_time,now_time,selected_date,date.today().isoformat())).fetchall()
    rooms=db.execute('''SELECT r.room_id resource_id,r.room_code resource_code,r.capacity,r.status,
        z.name zone_name,f.name floor_name,
        b.start_time,b.end_time,e.name employee_name
        FROM room r JOIN zone z ON z.zone_id=r.zone_id JOIN floor f ON f.floor_id=z.floor_id
        LEFT JOIN booking b ON b.booking_id=(SELECT b2.booking_id FROM booking b2
          WHERE b2.resource_type='ROOM' AND b2.resource_id=r.room_id
          AND b2.booking_date=? AND b2.status IN ('CONFIRMED','CHECKED_IN')
          AND ((?=? AND b2.start_time<=? AND b2.end_time>?) OR (?<>?))
          ORDER BY b2.start_time LIMIT 1)
        LEFT JOIN employee e ON e.employee_id=b.employee_id
        ORDER BY f.floor_number,z.name,r.room_code''',
        (selected_date,date.today().isoformat(),selected_date,now_time,now_time,selected_date,date.today().isoformat())).fetchall()
    return render_template('floor_map.html',desks=desks,rooms=rooms,selected_date=selected_date,
        available=sum(1 for d in desks if d['status']=='ACTIVE' and not d['start_time']),
        occupied=sum(1 for d in desks if d['status']=='ACTIVE' and d['start_time']),
        room_count=sum(1 for r in rooms if r['status']=='ACTIVE'))

@app.route('/resources')
@login_required
def resources():
    db=get_db()
    desks=db.execute('SELECT d.*,z.name zone_name,f.name floor_name FROM desk d JOIN zone z ON z.zone_id=d.zone_id JOIN floor f ON f.floor_id=z.floor_id ORDER BY d.desk_code').fetchall()
    rooms=db.execute('SELECT r.*,z.name zone_name FROM room r JOIN zone z ON z.zone_id=r.zone_id ORDER BY r.room_code').fetchall()
    return render_template('resources.html',desks=desks,rooms=rooms)

@app.route('/employees')
@login_required
@roles_required('ADMIN','FACILITY_MANAGER')
def employees():
    rows=get_db().execute('SELECT employee_id,name,email,role,department,status,created_at FROM employee ORDER BY name').fetchall()
    return render_template('employees.html',employees=rows)

@app.route('/employees/add',methods=['POST'])
@login_required
@roles_required('ADMIN')
def add_employee():
    name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower(); pw=request.form.get('password',''); role=request.form.get('role','EMPLOYEE'); dept=request.form.get('department','').strip()
    if not name or not email or len(pw)<8 or role not in ('EMPLOYEE','FACILITY_MANAGER','ADMIN'):
        flash('Enter valid details. Password must contain at least 8 characters.','danger')
    else:
        try:
            get_db().execute('INSERT INTO employee(name,email,password_hash,role,department) VALUES(?,?,?,?,?)',(name,email,hash_password(pw),role,dept)); flash('Employee added.','success')
        except sqlite3.IntegrityError: flash('Email already exists.','danger')
    return redirect(url_for('employees'))

@app.route('/reports')
@login_required
@roles_required('ADMIN','FACILITY_MANAGER')
def reports():
    db=get_db()
    daily=db.execute("SELECT booking_date,COUNT(*) total FROM booking WHERE status IN ('CONFIRMED','CHECKED_IN','COMPLETED') GROUP BY booking_date ORDER BY booking_date DESC LIMIT 7").fetchall()
    byzone=db.execute('''SELECT z.name zone_name,COUNT(b.booking_id) bookings FROM zone z LEFT JOIN desk d ON d.zone_id=z.zone_id LEFT JOIN room r ON r.zone_id=z.zone_id
      LEFT JOIN booking b ON (b.resource_type='DESK' AND b.resource_id=d.desk_id OR b.resource_type='ROOM' AND b.resource_id=r.room_id) AND b.status IN ('CONFIRMED','CHECKED_IN','COMPLETED')
      GROUP BY z.zone_id ORDER BY bookings DESC''').fetchall()
    utilization=db.execute("SELECT resource_type,COUNT(*) total_bookings,ROUND(AVG((julianday('2000-01-01 '||end_time)-julianday('2000-01-01 '||start_time))*24),2) avg_hours FROM booking WHERE status IN ('CONFIRMED','CHECKED_IN','COMPLETED') GROUP BY resource_type").fetchall()
    return render_template('reports.html',daily=daily,byzone=byzone,utilization=utilization)

@app.route('/queries')
@login_required
@roles_required('ADMIN','FACILITY_MANAGER')
def queries():
    db=get_db()
    peak=db.execute("SELECT start_time,COUNT(*) bookings FROM booking WHERE status IN ('CONFIRMED','CHECKED_IN') GROUP BY start_time ORDER BY bookings DESC LIMIT 5").fetchall()
    low=db.execute("SELECT 'DESK' type,desk_code code FROM desk d WHERE NOT EXISTS(SELECT 1 FROM booking b WHERE b.resource_type='DESK' AND b.resource_id=d.desk_id AND b.status IN ('CONFIRMED','CHECKED_IN','COMPLETED')) UNION ALL SELECT 'ROOM',room_code FROM room r WHERE NOT EXISTS(SELECT 1 FROM booking b WHERE b.resource_type='ROOM' AND b.resource_id=r.room_id AND b.status IN ('CONFIRMED','CHECKED_IN','COMPLETED'))").fetchall()
    no_show=db.execute("SELECT e.name,b.booking_date,b.start_time,b.end_time FROM booking b JOIN employee e ON e.employee_id=b.employee_id WHERE b.status='CONFIRMED' AND b.booking_date<date('now','localtime') ORDER BY b.booking_date DESC LIMIT 20").fetchall()
    large_rooms=db.execute("SELECT room_code,capacity FROM room WHERE capacity>=20 AND status='ACTIVE' ORDER BY capacity DESC").fetchall()
    return render_template('queries.html',peak=peak,low=low,no_show=no_show,large_rooms=large_rooms)

@app.route('/access-logs')
@login_required
@roles_required('ADMIN','FACILITY_MANAGER')
def access_logs():
    rows=get_db().execute('SELECT l.*,e.name FROM access_log l JOIN employee e ON e.employee_id=l.employee_id ORDER BY l.created_at DESC LIMIT 100').fetchall()
    return render_template('logs.html',logs=rows)

@app.route('/api/availability')
@login_required
def api_availability():
    typ=request.args.get('type','DESK'); rid=request.args.get('id',type=int); day=request.args.get('date'); start=request.args.get('start'); end=request.args.get('end')
    if typ not in ('DESK','ROOM') or not rid or not day or not start or not end: return jsonify({'available':False,'error':'Missing parameters'}),400
    row=get_db().execute("SELECT 1 FROM booking WHERE resource_type=? AND resource_id=? AND booking_date=? AND status IN ('CONFIRMED','CHECKED_IN') AND start_time < ? AND end_time > ? LIMIT 1",(typ,rid,day,end,start)).fetchone()
    return jsonify({'available':row is None})

@app.errorhandler(404)
def not_found(e): return render_template('error.html',message='Page not found.'),404

if __name__=='__main__':
    init_db()
    app.run(host='127.0.0.1',port=int(os.environ.get('PORT',5000)),debug=True)
