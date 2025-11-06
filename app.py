import os
import logging
import datetime
import json
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import generate_password_hash, check_password_hash

import psycopg
from psycopg.rows import dict_row
import psycopg.errors as pg_errors
from psycopg_pool import ConnectionPool

# -------------------------
# Flask App Setup
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
logging.basicConfig(level=logging.INFO)

# -------------------------
# Required environment variables
# -------------------------
required_env = ["SECRET_KEY", "DATABASE_URL", "MAIL_USERNAME", "SMTP_PASSWORD"]
for v in required_env:
    if v not in os.environ:
        raise RuntimeError(f"Missing required environment variable: {v}")

# Load environment variables
app.secret_key = os.environ["SECRET_KEY"]
DB_URL_RAW = os.environ["DATABASE_URL"]
MAIL_USERNAME = os.environ["MAIL_USERNAME"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]
DEBUG = os.environ.get("DEBUG", "False").lower() in ("1", "true", "yes")

# Fix Postgres scheme (psycopg expects postgresql://)
DB_URL = DB_URL_RAW.replace("postgres://", "postgresql://", 1) if DB_URL_RAW.startswith("postgres://") else DB_URL_RAW

# -------------------------
# Database connection pool
# -------------------------
POOL_MAX = int(os.environ.get("DB_POOL_MAX", 6))
try:
    # Use dict_row factory globally for easy dict access
    pool = ConnectionPool(conninfo=DB_URL, max_size=POOL_MAX, row_factory=dict_row)
    app.logger.info("Postgres connection pool created (max_size=%s).", POOL_MAX)
except Exception:
    app.logger.exception("Failed to create Postgres connection pool; using direct connections.")
    pool = None

def get_conn():
    """Returns a connection context manager (from pool or direct)."""
    if pool:
        return pool.connection()
    # Fallback to direct connection
    class _DirectConnCtx:
        def __enter__(self):
            self.conn = psycopg.connect(DB_URL, row_factory=dict_row)
            return self.conn
        def __exit__(self, exc_type, exc, tb):
            try:
                if exc_type:
                    self.conn.rollback()
                else:
                    self.conn.commit()
            finally:
                self.conn.close()
    return _DirectConnCtx()

# -------------------------
# Flask-Mail Setup & Security
# -------------------------
app.config.update(
    MAIL_SERVER="smtp.gmail.com",
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=MAIL_USERNAME,
    MAIL_PASSWORD=SMTP_PASSWORD,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)
mail = Mail(app)
serializer = URLSafeTimedSerializer(app.secret_key)

# -------------------------
# Database Initialization
# -------------------------
def init_tables():
    """Ensures all necessary tables exist on startup."""
    try:
        with get_conn() as conn, conn.cursor() as cur:
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
            cur.execute("""
            CREATE TABLE IF NOT EXISTS sensordata1 (
                id SERIAL PRIMARY KEY,
                datetime TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                food VARCHAR(266),
                water VARCHAR(266)
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
            cur.execute("""
            CREATE TABLE IF NOT EXISTS chickstatus (
                id SERIAL PRIMARY KEY,
                ChickNumber VARCHAR(266),
                status VARCHAR(100),
                DateTime TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            )
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                message TEXT,
                DateTime TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            )
            """)
            # NOTE: Tables `sensordata2` (conveyor, sprinkle, uvlight), `feeding_schedule`, and `chickens` were omitted 
            # as they are not used by the existing JS, but you may re-add them if needed.

    except Exception:
        app.logger.exception("init_tables: failed to ensure tables")

init_tables()

# -------------------------
# Decorators & Utilities
# -------------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def role_required(roles):
    if not isinstance(roles, (list, tuple)):
        roles = [roles]
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user_role = session.get("user_role")
            if "user_id" not in session or user_role not in roles:
                flash("Access denied. You do not have the required permissions.", "danger")
                return redirect(url_for("dashboard")) # Redirect to a safe page
            return f(*args, **kwargs)
        return wrapper
    return decorator

def format_datetime_in_results(results, field_name="datetime"):
    """Helper to format datetime fields in a list of dicts for tables."""
    for result in results:
        # Check if the row uses 'datetime' or 'DateTime'
        dt_key = field_name if field_name in result else 'DateTime'
        
        if result.get(dt_key):
            try:
                original_datetime = result[dt_key]
                if isinstance(original_datetime, datetime.datetime):
                    # Format as 'YYYY-MM-DD HH:MM:SS AM/PM'
                    formatted_datetime = original_datetime.strftime("%Y-%m-%d %I:%M:%S %p")
                else:
                    # Try parsing from string
                    parsed = datetime.datetime.fromisoformat(str(original_datetime))
                    formatted_datetime = parsed.strftime("%Y-%m-%d %I:%M:%S %p")
                result[dt_key] = formatted_datetime
            except Exception:
                # Keep original string if parsing fails
                result[dt_key] = str(result[dt_key])
    return results

# -------------------------
# Frontend Routes (Rendering Templates)
# -------------------------

@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, username, password, role FROM users WHERE email = %s", (email,))
            user = cur.fetchone()

            if user and check_password_hash(user["password"], password):
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["user_role"] = user["role"]
                flash("Login successful.", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        hashed = generate_password_hash(password)

        try:
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (username,email,password,role) VALUES (%s,%s,%s,%s)",
                    (username, email, hashed, "user")
                )
        except pg_errors.UniqueViolation:
            flash("Email already registered.", "danger")
        except Exception:
            app.logger.exception("Registration failed")
            flash("Database error. Try again later.", "danger")
        else:
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    # This route will render your main dashboard template
    return render_template("dashboard.html")

@app.route("/admin-dashboard")
@role_required(("admin","superadmin"))
def admin_dashboard():
    # This route will render the admin-specific dashboard
    return render_template("admin-dashboard.html")

@app.route("/report")
@login_required
def report_page():
    # This route is for your reports page with all the tables
    return render_template("report.html")

@app.route("/manage_users")
@role_required(("admin","superadmin"))
def manage_users_page():
    # This route is for the manage users page with the modal logic
    return render_template("manage_users.html")

# -------------------------
# API Routes (Data Fetching & Control)
# -------------------------

@app.route('/data')
def fetch_realtime_data():
    """
    FIX: Combines latest environment data (sensordata) and level data (sensordata4)
    into a single payload for charts, status cards, and gauges, matching the JS keys.
    """
    latest_data = {}
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # 1. Get latest environment data (Temp, Hum, Amm, Lights, Fan)
            cur.execute("SELECT temperature, humidity, ammonia, light1, light2, exhaustfan FROM sensordata ORDER BY id DESC LIMIT 1")
            env_data = cur.fetchone()

            # 2. Get latest level data (Water_Level, Food_Level)
            cur.execute("SELECT water_level, food_level FROM sensordata4 ORDER BY id DESC LIMIT 1")
            level_data = cur.fetchone()

        if env_data:
            latest_data.update({
                "Temp": env_data.get("temperature", 0.0),
                "Hum": env_data.get("humidity", 0.0),
                "Amm": env_data.get("ammonia", 0.0),
                "Light1": env_data.get("light1", "OFF"),
                "Light2": env_data.get("light2", "OFF"),
                "ExhaustFan": env_data.get("exhaustfan", "OFF"),
            })

        if level_data:
             latest_data.update({
                "Water_Level": level_data.get("water_level", 0.0),
                "Food_Level": level_data.get("food_level", 0.0),
            })
            
        if not latest_data:
            return jsonify({'error': 'No recent sensor data available.'}), 404

        return jsonify(latest_data)
    except Exception as e:
        app.logger.exception("Error in /data realtime fetch")
        return jsonify({'error': str(e)}), 500

@app.route('/get_growth_data')
def fetch_growth_data():
    """Fetches the latest weight for the dashboard card."""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Fetches the latest single record for the Weight card update
            cur.execute("SELECT DateTime, ChickNumber, Weight FROM sensordata3 ORDER BY DateTime DESC LIMIT 1")
            results = cur.fetchall()
            # The JS expects an array of one item for the latest data[0]
            return jsonify(results) 
    except Exception as e:
        app.logger.exception("Error in /get_growth_data")
        return jsonify({'error': str(e)}), 500

@app.route('/get_supplies_data') # Alias for former /get_all_data3
def fetch_supplies_data():
    """Fetches Food/Water stock log from sensordata1 for the Supplies Stock table."""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT DateTime, Food, Water FROM sensordata1 ORDER BY DateTime DESC LIMIT 50")
            results = cur.fetchall()
            results = format_datetime_in_results(results, "DateTime")
            return jsonify(results)
    except Exception as e:
        app.logger.exception("Error in /get_supplies_data")
        return jsonify({'error': str(e)})

@app.route('/get_environment_data') # Alias for former /get_all_data5
def fetch_environment_data():
    """Fetches Environment data from sensordata for the Environment Table."""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT DateTime, Humidity, Temperature, Ammonia, Light1, Light2, ExhaustFan FROM sensordata ORDER BY DateTime DESC LIMIT 50")
            results = cur.fetchall()
            results = format_datetime_in_results(results, "DateTime")
            return jsonify(results)
    except Exception as e:
        app.logger.exception("Error in /get_environment_data")
        return jsonify({'error': str(e)}), 500

@app.route('/get_chickstatus_data') # Alias for former /get_all_data6
def fetch_chickstatus_data():
    """Fetches Chick Health Status from chickstatus for the Diagnostic Health Table."""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT DateTime, ChickNumber, status FROM chickstatus ORDER BY DateTime DESC LIMIT 50")
            results = cur.fetchall()
            results = format_datetime_in_results(results, "DateTime")
            return jsonify(results)
    except Exception as e:
        app.logger.exception("Error in /get_chickstatus_data")
        return jsonify({'error': str(e)}), 500

@app.route('/get_notifications_data') # Alias for former /get_all_data7
def fetch_notifications_data():
    """Fetches Notifications log for the Notifications Table."""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT DateTime, message FROM notifications ORDER BY DateTime DESC LIMIT 50")
            results = cur.fetchall()
            results = format_datetime_in_results(results, "DateTime")
            return jsonify(results)
    except Exception as e:
        app.logger.exception("Error in /get_notifications_data")
        return jsonify({'error': str(e)}), 500

@app.route('/get_users') # New route for Manage Users page
@role_required(("admin","superadmin"))
def get_users():
    """Fetches all users for the Manage Users table."""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, email, username, role FROM users ORDER BY id ASC")
            results = cur.fetchall()
            return jsonify(results)
    except Exception as e:
        app.logger.exception("Error in /get_users")
        return jsonify({'error': str(e)}), 500

@app.route('/update_user/<int:user_id>', methods=['POST'])
@role_required(("admin","superadmin"))
def update_user(user_id):
    """Handles the user update submission from the edit modal."""
    data = request.get_json()
    email = data.get('email')
    username = data.get('username')
    password = data.get('password') # May be empty
    
    if not email or not username:
        return jsonify({'success': False, 'message': 'Email and username are required.'}), 400

    try:
        with get_conn() as conn, conn.cursor() as cur:
            if password:
                hashed_password = generate_password_hash(password)
                cur.execute(
                    "UPDATE users SET email = %s, username = %s, password = %s WHERE id = %s",
                    (email, username, hashed_password, user_id)
                )
            else:
                 cur.execute(
                    "UPDATE users SET email = %s, username = %s WHERE id = %s",
                    (email, username, user_id)
                )
        return jsonify({'success': True, 'message': f'User {user_id} updated successfully.'})

    except pg_errors.UniqueViolation:
        return jsonify({'success': False, 'message': 'Email already exists.'}), 409
    except Exception as e:
        app.logger.exception(f"Error updating user {user_id}")
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@role_required(("admin","superadmin"))
def delete_user(user_id):
    """Handles the user deletion request."""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            if cur.rowcount == 0:
                 return jsonify({'success': False, 'message': f'User {user_id} not found.'}), 404
        return jsonify({'success': True, 'message': f'User {user_id} deleted successfully.'})
    except Exception as e:
        app.logger.exception(f"Error deleting user {user_id}")
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500


@app.route('/api/notifications', methods=['POST'])
def save_notifications():
    """Handles saving new notifications from the frontend (JS localStorage)."""
    try:
        data = request.get_json()
        notifications = data.get('notifications', [])
        
        # Only save new, unseen notifications to the database.
        # This implementation simply logs all notifications received from the JS local storage.
        # A more complex system would deduplicate against existing DB entries.

        with get_conn() as conn, conn.cursor() as cur:
            for message in notifications:
                # Insert the message with the current timestamp
                cur.execute(
                    "INSERT INTO notifications (message) VALUES (%s)",
                    (message,)
                )
        return jsonify({"success": True, "count": len(notifications)})
    except Exception as e:
        app.logger.exception("Error saving notifications to backend")
        return jsonify({"success": False, "error": str(e)}), 500


# -------------------------
# Run App
# -------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=DEBUG)
