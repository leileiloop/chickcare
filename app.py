from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
import logging
import psycopg
from psycopg.rows import dict_row
import psycopg.errors as pg_errors
import datetime

# -------------------------
# Flask App Setup
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
logging.basicConfig(level=logging.INFO)

# -------------------------
# Environment Variables (required)
# -------------------------
required_env = ["SECRET_KEY", "DATABASE_URL", "MAIL_USERNAME", "SMTP_PASSWORD"]
missing_env = [v for v in required_env if v not in os.environ]
if missing_env:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing_env)}")

app.secret_key = os.environ["SECRET_KEY"]
DB_URL_RAW = os.environ["DATABASE_URL"]
MAIL_USERNAME = os.environ["MAIL_USERNAME"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]

# Fix Postgres URL for psycopg if needed
DB_URL = DB_URL_RAW.replace("postgres://", "postgresql://", 1) if DB_URL_RAW.startswith("postgres://") else DB_URL_RAW

# -------------------------
# Flask-Mail Setup
# -------------------------
app.config.update(
    MAIL_SERVER="smtp.gmail.com",
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=MAIL_USERNAME,
    MAIL_PASSWORD=SMTP_PASSWORD
)
mail = Mail(app)
serializer = URLSafeTimedSerializer(app.secret_key)

# -------------------------
# Session Security
# -------------------------
# Note: SESSION_COOKIE_SECURE=True requires HTTPS; keep as you had it.
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)

# -------------------------
# Database Helper
# -------------------------
def get_conn():
    """Return a psycopg connection with dict row factory"""
    return psycopg.connect(DB_URL, row_factory=dict_row)

# -------------------------
# Auto Table Creation (safe, will not drop existing)
# -------------------------
def init_tables():
    """Create lightweight fallback tables if they do not exist.
    This helps avoid runtime failures when a table is missing on a fresh DB.
    It intentionally matches/overlaps the table names your templates and routes expect.
    """
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # users table (matches your usage)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(266) NOT NULL,
                    email VARCHAR(266) UNIQUE NOT NULL,
                    password VARCHAR(266) NOT NULL,
                    role TEXT DEFAULT 'user',
                    reset_token TEXT
                )
            """)
            # sensordata (environment) - some schemas use 'datetime', others 'timestamp'
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sensordata (
                    id SERIAL PRIMARY KEY,
                    datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                    humidity REAL,
                    temperature REAL,
                    ammonia REAL,
                    light1 VARCHAR(266),
                    light2 VARCHAR(266),
                    exhaustfan VARCHAR(266)
                )
            """)
            # sensordata1..4 (kept minimal so your routes that query them don't crash)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sensordata1 (
                    id SERIAL PRIMARY KEY,
                    datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                    food VARCHAR(266),
                    water VARCHAR(266)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sensordata2 (
                    id SERIAL PRIMARY KEY,
                    datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                    conveyor VARCHAR(266),
                    sprinkle VARCHAR(266),
                    uvlight VARCHAR(266)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sensordata3 (
                    id SERIAL PRIMARY KEY,
                    datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                    chicknumber VARCHAR(266),
                    weight REAL,
                    weighingcount INTEGER DEFAULT 0,
                    averageweight DECIMAL(8,3) DEFAULT 0.000
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sensordata4 (
                    id SERIAL PRIMARY KEY,
                    water_level REAL,
                    food_level REAL,
                    datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
                )
            """)
            # feeding_schedule (some templates/queries expect this)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS feeding_schedule (
                    id SERIAL PRIMARY KEY,
                    feed_time TIMESTAMP WITHOUT TIME ZONE,
                    feed_type VARCHAR(266),
                    amount FLOAT
                )
            """)
            # chickens (some dashboard queries expect chickens)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chickens (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100),
                    age INTEGER,
                    weight FLOAT
                )
            """)
            conn.commit()
        app.logger.info("init_tables: ensured fallback tables exist.")
    except Exception:
        app.logger.exception("init_tables: failed to ensure tables")

# Initialize fallback tables (safe)
init_tables()

# -------------------------
# Short helpers
# -------------------------
def normalize_env_records(rows):
    """Normalize returned rows to have keys used by your templates:
       - temperature, humidity, date, time
       Accepts dict_row or list of dict-like objects and returns list of dicts.
    """
    normalized = []
    for r in rows:
        # r may be a dict_row with keys like 'datetime' or 'timestamp'
        try:
            # convert to a plain dict in case it's a psycopg dict_row
            rec = dict(r)
        except Exception:
            rec = r

        # find a datetime value
        dt = None
        if "datetime" in rec and rec["datetime"] is not None:
            dt = rec["datetime"]
        elif "timestamp" in rec and rec["timestamp"] is not None:
            dt = rec["timestamp"]
        elif "date" in rec and rec["date"] is not None and isinstance(rec["date"], datetime.datetime):
            dt = rec["date"]

        date_str = ""
        time_str = ""
        if isinstance(dt, datetime.datetime):
            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%H:%M:%S")
        else:
            # fallback: attempt to coerce strings
            try:
                parsed = datetime.datetime.fromisoformat(str(dt))
                date_str = parsed.strftime("%Y-%m-%d")
                time_str = parsed.strftime("%H:%M:%S")
            except Exception:
                date_str = str(rec.get("datetime") or rec.get("timestamp") or "")
                time_str = ""

        normalized.append({
            "temperature": rec.get("temperature") if rec.get("temperature") is not None else rec.get("temp"),
            "humidity": rec.get("humidity"),
            "ammonia": rec.get("ammonia"),
            "light1": rec.get("light1"),
            "light2": rec.get("light2"),
            "exhaustfan": rec.get("exhaustfan"),
            "date": date_str,
            "time": time_str,
            # also keep raw record in case templates expect other fields
            **rec
        })
    return normalized

# -------------------------
# Decorators
# -------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def wrapper(*args, **kwargs):
            if session.get("user_role") not in roles:
                flash("You do not have permission to access this page.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return wrapper
    return decorator

# -------------------------
# User Helpers
# -------------------------
def get_user_by_email(email):
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email=%s", (email,))
            return cur.fetchone()
    except Exception:
        app.logger.exception("Error fetching user by email")
        return None

def get_user_by_id(user_id):
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
            return cur.fetchone()
    except Exception:
        app.logger.exception("Error fetching user by ID")
        return None

def get_current_user():
    user_id = session.get("user_id")
    return get_user_by_id(user_id) if user_id else None

def create_superadmin():
    """Create default superadmin if none exists"""
    super_email = "superadmin@example.com"
    super_username = "admin"
    super_pass = generate_password_hash("admin")
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE role='superadmin' LIMIT 1")
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO users (username,email,password,role) VALUES (%s,%s,%s,%s)",
                    (super_username, super_email, super_pass, "superadmin")
                )
                conn.commit()
                app.logger.info("Superadmin created")
            else:
                app.logger.info("Superadmin already exists")
    except Exception:
        app.logger.exception("Failed to create superadmin")

# Create once (safe if already exists)
create_superadmin()

# -------------------------
# Routes
# -------------------------
@app.route("/")
def home():
    role = session.get("user_role")
    if role in ["admin", "superadmin"]:
        return redirect(url_for("admin_dashboard"))
    elif role:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

# ----- Auth -----
@app.route("/login", methods=["GET","POST"])
def login():
    if "user_id" in session:
        role = session.get("user_role")
        return redirect(url_for("admin_dashboard") if role in ["admin","superadmin"] else url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email","").strip()
        password = request.form.get("password","")
        user = get_user_by_email(email)
        if user and check_password_hash(user["password"], password):
            session.update({
                "user_id": user["id"],
                "user_role": user.get("role","user"),
                "user_username": user.get("username"),
                "user_email": user.get("email")
            })
            flash(f"Welcome, {user.get('username','User')}!", "success")
            return redirect(url_for("admin_dashboard") if user.get("role") in ["admin","superadmin"] else url_for("dashboard"))
        flash("Invalid email or password", "danger")
    return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if "user_id" in session:
        role = session.get("user_role")
        return redirect(url_for("admin_dashboard") if role in ["admin","superadmin"] else url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username","").strip()
        email = request.form.get("email","").strip()
        password = request.form.get("password","")
        if not username or not email or not password:
            flash("All fields are required.", "warning")
            return redirect(url_for("register"))
        hashed = generate_password_hash(password)
        try:
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (username,email,password,role) VALUES (%s,%s,%s,%s)",
                    (username,email,hashed,"user")
                )
                conn.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except pg_errors.UniqueViolation:
            flash("Email already registered.", "danger")
        except Exception:
            app.logger.exception("Registration failed")
            flash("Database error. Try again later.", "danger")
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))

# ----- Dashboard -----
@app.route("/dashboard")
@login_required
def dashboard():
    records = []
    total_chickens = 0
    temperature = 0
    humidity = 0
    upcoming_feeding = "N/A"

    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Fetch recent environment rows (if table exists)
            try:
                cur.execute("SELECT * FROM sensordata ORDER BY id DESC LIMIT 5")
                raw = cur.fetchall()
                # normalize for templates (date/time keys)
                records = normalize_env_records(raw)
            except psycopg.errors.UndefinedTable:
                app.logger.warning("Table 'sensordata' does not exist.")

            # Total chickens (if table exists)
            try:
                cur.execute("SELECT COUNT(*) AS total FROM chickens")
                res = cur.fetchone()
                total_chickens = int(res["total"]) if res and res.get("total") is not None else 0
            except psycopg.errors.UndefinedTable:
                app.logger.warning("Table 'chickens' does not exist.")

            # Use most recent record for temperature/humidity if available
            if records:
                temperature = records[0].get("temperature", 0) or 0
                humidity = records[0].get("humidity", 0) or 0

            # Next feeding (if table exists)
            try:
                cur.execute("SELECT feed_time FROM feeding_schedule WHERE feed_time > NOW() ORDER BY feed_time ASC LIMIT 1")
                feed = cur.fetchone()
                if feed and feed.get("feed_time"):
                    # feed_time may be datetime object
                    ft = feed["feed_time"]
                    if isinstance(ft, datetime.datetime):
                        upcoming_feeding = ft.strftime("%H:%M")
                    else:
                        # try parse
                        try:
                            parsed = datetime.datetime.fromisoformat(str(ft))
                            upcoming_feeding = parsed.strftime("%H:%M")
                        except Exception:
                            upcoming_feeding = str(ft)
            except psycopg.errors.UndefinedTable:
                app.logger.warning("Table 'feeding_schedule' does not exist.")
    except Exception:
        app.logger.exception("Failed to fetch dashboard data")
        flash("Could not load dashboard data.", "warning")

    return render_template(
        "dashboard.html",
        records=records,
        total_chickens=total_chickens,
        temperature=temperature,
        humidity=humidity,
        upcoming_feeding=upcoming_feeding
    )

@app.route("/admin-dashboard")
@role_required("admin","superadmin")
def admin_dashboard():
    # Example admin metrics - try to load simple counts where possible
    active_users = 0
    reports_count = 0
    active_farms = 0
    alerts_count = 0
    recent_activities = []
    try:
        with get_conn() as conn, conn.cursor() as cur:
            try:
                cur.execute("SELECT COUNT(*) AS c FROM users")
                r = cur.fetchone()
                active_users = int(r["c"]) if r and r.get("c") is not None else 0
            except Exception:
                app.logger.debug("admin_dashboard: users count failed")
            # recent activity fallback: use sensordata or sensordata1 timestamps to show some activity
            try:
                cur.execute("SELECT id, datetime FROM sensordata ORDER BY id DESC LIMIT 5")
                rows = cur.fetchall()
                for row in rows:
                    dt = row.get("datetime") or row.get("timestamp") or ""
                    recent_activities.append({"user":"system","action":"sensordata inserted","date": str(dt)})
            except Exception:
                app.logger.debug("admin_dashboard: recent activities fetch failed")
    except Exception:
        app.logger.exception("admin_dashboard: error")

    return render_template("admin-dashboard.html",
                           active_users=active_users,
                           reports_count=reports_count,
                           active_farms=active_farms,
                           alerts_count=alerts_count,
                           recent_activities=recent_activities)

# ----- Profile & Settings -----
@app.route("/profile")
@login_required
def profile():
    user = get_current_user()
    return render_template("profile.html", user=user)

@app.route("/settings", methods=["GET","POST"])
@login_required
def settings():
    user = get_current_user()
    if request.method == "POST":
        username = request.form.get("username","").strip()
        email = request.form.get("email","").strip()
        new_pass = request.form.get("password","")
        if not username or not email:
            flash("Username and email cannot be empty.", "warning")
            return redirect(url_for("settings"))
        try:
            with get_conn() as conn, conn.cursor() as cur:
                if new_pass:
                    cur.execute(
                        "UPDATE users SET username=%s,email=%s,password=%s WHERE id=%s",
                        (username,email,generate_password_hash(new_pass),user["id"])
                    )
                else:
                    cur.execute(
                        "UPDATE users SET username=%s,email=%s WHERE id=%s",
                        (username,email,user["id"])
                    )
                conn.commit()
            session.update({"user_username":username,"user_email":email})
            flash("Settings updated successfully.", "success")
            return redirect(url_for("settings"))
        except Exception:
            app.logger.exception("Failed to update settings")
            flash("Update failed. Try again later.", "danger")
    return render_template("settings.html", user=user)

# ----- Manage Users -----
@app.route("/manage-users")
@role_required("admin","superadmin")
def manage_users():
    users = []
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT id,username,email,role FROM users ORDER BY id DESC")
            users = cur.fetchall()
    except Exception:
        app.logger.exception("Failed to load users")
    return render_template("manage-users.html", users=users)

# ----- Password Reset -----
@app.route("/generate", methods=["GET","POST"])
def generate():
    if request.method == "POST":
        email = request.form.get("email","").strip()
        user = get_user_by_email(email)
        if user:
            try:
                token = serializer.dumps(email, salt="password-reset-salt")
                reset_url = url_for("reset_with_token", token=token, _external=True)
                msg = Message(
                    "ChickCare Password Reset",
                    sender=MAIL_USERNAME,
                    recipients=[email],
                    body=f"Hi {user['username']},\nClick the link below to reset your password:\n{reset_url}\nIf you didn't request this, ignore this email."
                )
                mail.send(msg)
                flash("Password reset link sent! Check your email.", "info")
            except Exception:
                app.logger.exception("Failed to send email")
                flash("Failed to send reset email. Try again later.", "danger")
        else:
            flash("Email not found.", "warning")
    return render_template("generate.html")

@app.route("/reset/<token>", methods=["GET","POST"])
def reset_with_token(token):
    try:
        email = serializer.loads(token, salt="password-reset-salt", max_age=3600)
    except SignatureExpired:
        flash("The link has expired.", "danger")
        return redirect(url_for("generate"))
    except BadSignature:
        flash("Invalid or tampered token.", "danger")
        return redirect(url_for("generate"))

    if request.method == "POST":
        password = request.form.get("password","")
        if not password:
            flash("Password cannot be empty.", "warning")
            return redirect(url_for("reset_with_token", token=token))
        try:
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET password=%s WHERE email=%s",
                    (generate_password_hash(password), email)
                )
                conn.commit()
            flash("Password reset successful! You can now log in.", "success")
            return redirect(url_for("login"))
        except Exception:
            app.logger.exception("Password reset failed")
            flash("Could not reset password. Try again later.", "danger")
    return render_template("reset_password.html", token=token)

# ----- Feature Pages -----
@app.route("/growth-monitoring")
@login_required
def growth_monitoring():
    # Some older templates used url_for('feeding_schedule') (BuildError). Provide alias route below.
    return render_template("growth.html")

# --- Alias for older templates that reference feeding_schedule endpoint name ---
@app.route("/feeding_schedule")
def feeding_schedule_alias():
    """
    Some templates (older) call url_for('feeding_schedule') — this alias keeps backward compatibility.
    It delegates to the current feed_schedule view.
    """
    return feed_schedule()

# Keep your original feed-schedule route (templates use 'feed_schedule')
@app.route("/feed-schedule")
@login_required
def feed_schedule():
    feeding_schedule = []
    try:
        with get_conn() as conn, conn.cursor() as cur:
            try:
                cur.execute("SELECT id, feed_time, feed_type, amount FROM feeding_schedule ORDER BY feed_time ASC")
                raw = cur.fetchall()
                # normalize feed_time to readable strings for templates
                feeding_schedule = []
                for r in raw:
                    rec = dict(r)
                    ft = rec.get("feed_time")
                    if isinstance(ft, datetime.datetime):
                        rec["time"] = ft.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        rec["time"] = str(ft)
                    # compatibility with templates expecting .time, .feed_type, .amount
                    rec["feed_type"] = rec.get("feed_type") or rec.get("type") or ""
                    rec["amount"] = rec.get("amount") or 0
                    feeding_schedule.append(rec)
            except psycopg.errors.UndefinedTable:
                app.logger.warning("Table 'feeding_schedule' does not exist.")
    except Exception:
        app.logger.exception("Failed to load feeding data")
        flash("Could not load feeding data.", "warning")
    return render_template("feeding.html", feeding_schedule=feeding_schedule)

@app.route("/environment")
@login_required
def environment():
    environment_data = []
    try:
        with get_conn() as conn, conn.cursor() as cur:
            try:
                cur.execute("SELECT * FROM sensordata ORDER BY id DESC LIMIT 50")
                raw = cur.fetchall()
                environment_data = normalize_env_records(raw)
            except psycopg.errors.UndefinedTable:
                app.logger.warning("Table 'sensordata' does not exist.")
    except Exception:
        app.logger.exception("Failed to load environment data")
        flash("Could not load environment data.", "warning")
    return render_template("environment.html", environment_data=environment_data)

@app.route("/sanitization")
@login_required
def sanitization():
    return render_template("sanitization.html")

@app.route("/report")
@login_required
def report():
    return render_template("report.html")

@app.route("/data-table")
@login_required
def data_table():
    data_table_records = []
    try:
        with get_conn() as conn, conn.cursor() as cur:
            try:
                cur.execute("SELECT * FROM sensordata ORDER BY id DESC")
                raw = cur.fetchall()
                data_table_records = normalize_env_records(raw)
            except psycopg.errors.UndefinedTable:
                app.logger.warning("Table 'sensordata' does not exist.")
    except Exception:
        app.logger.exception("Failed to fetch data table")
        flash("Could not load data.", "warning")
    return render_template("data_table.html", data=data_table_records)

# -------------------------
# Run App
# -------------------------
if __name__ == "__main__":
    # Keep debug True for now (as in your original), but set to False in production if you want.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
