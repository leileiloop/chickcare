import os
import secrets
import json # Import for JSON responses in new routes
from flask import Flask, render_template, jsonify, request, session, flash, redirect, url_for
import psycopg
from psycopg.rows import dict_row
from psycopg.errors import UniqueViolation, OperationalError
from werkzeug.security import generate_password_hash, check_password_hash
import functools

# -------------------------
# App Configuration
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey") # Change in production

# -------------------------
# PostgreSQL Configuration
# -------------------------
DATABASE_URL = os.environ.get("DATABASE_URL") 

def get_db_connection():
    """
    Connect to PostgreSQL with SSL. 
    Appends 'sslmode=require' to the URL and fixes the scheme for Render compatibility.
    """
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is not set. Cannot establish database connection.")
    
    connection_string_with_ssl = DATABASE_URL
    
    # --- FIX 0: STRIP ACCIDENTAL VARIABLE PREFIX (New defensive measure) ---
    if connection_string_with_ssl.startswith("DATABASE_URL="):
        connection_string_with_ssl = connection_string_with_ssl.split("=", 1)[1]
    
    # --- FIX 1: Correct the connection scheme for psycopg (Required for Render/Heroku) ---
    if connection_string_with_ssl.startswith("postgres://"):
        connection_string_with_ssl = connection_string_with_ssl.replace("postgres://", "postgresql://", 1)
    
    # --- FIX 2: Ensure sslmode=require is appended (User's existing logic) ---
    if "sslmode" not in connection_string_with_ssl:
        if "?" in connection_string_with_ssl:
            connection_string_with_ssl += "&sslmode=require"
        else:
            connection_string_with_ssl += "?sslmode=require"
    
    try:
        return psycopg.connect(connection_string_with_ssl, row_factory=dict_row)
    except OperationalError as e:
        # Crucial for debugging connection issues
        print(f"CRITICAL: Database connection failed. Details: {e}")
        raise ConnectionError(f"Database connection failed: Check the DATABASE_URL value and network access. Details: {e}")

# -------------------------
# Utility Functions & Decorators
# -------------------------

def login_required(view):
    """Decorator to check if a user is logged in."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if "user_role" not in session:
            flash("You need to log in to view this page.", "warning")
            return redirect(url_for("login"))
        return view(**kwargs)
    return wrapped_view

def list_shots():
    """Return a list of image files in static/shots."""
    shots_dir = os.path.join(app.static_folder, "shots")
    if os.path.exists(shots_dir):
        # Filter for images and return only file names
        return [f for f in os.listdir(shots_dir) if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif"))]
    return []

# -------------------------
# Authentication Routes
# -------------------------
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            error = "Please provide username and password."
            print("LOGIN FAIL: Missing username or password.")
        elif username.lower() == "admin" and password == "admin":
            session["user_role"] = "admin"
            session["email"] = "admin@yourdomain.com"
            flash("Admin login successful!", "success")
            print("LOGIN SUCCESS: Admin logged in.")
            return redirect(url_for("dashboard"))
        else:
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        # Use lower() for case-insensitive username lookup if your DB is case-sensitive
                        cur.execute("SELECT * FROM users WHERE Username=%s", (username,))
                        user = cur.fetchone()
                        
                        if user:
                            print(f"LOGIN ATTEMPT: User '{username}' found in DB.")
                            # NOTE: This uses raw password comparison based on the provided SQL setup.
                            if user["Password"] == password: 
                                print("LOGIN SUCCESS: Password matched.")
                                session["user_role"] = "user"
                                session["email"] = user["Email"]
                                flash("Login successful!", "success")
                                print("LOGIN: Session set, redirecting to dashboard.")
                                return redirect(url_for("dashboard"))
                            else:
                                print("LOGIN FAIL: Password mismatch.")
                                error = "Invalid credentials."
                        else:
                            print(f"LOGIN FAIL: User '{username}' not found.")
                            error = "Invalid credentials."
            except (ValueError, ConnectionError, Exception) as e:
                # Log critical failure
                print(f"CRITICAL LOGIN DB ERROR: {e}")
                error = f"Login failed due to application error: {e}" 

    return render_template("login.html", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not email or not username or not password:
            flash("Please fill all fields.", "warning")
            return redirect(url_for("register"))

        raw_password = password 

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO users (Email, Username, Password) VALUES (%s, %s, %s)",
                        (email, username, raw_password)
                    )
                conn.commit()
            
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
            
        except UniqueViolation:
            # This should catch the error if the schema was applied correctly
            flash("Username or Email already taken.", "danger")
            print(f"REGISTRATION FAIL: Unique constraint violated for {username} or {email}.")
        except (ValueError, ConnectionError, Exception) as e:
            # Catch other potential database errors
            print(f"REGISTRATION FAIL: DB Error: {e}")
            flash(f"Registration failed: Database error. {e}", "danger")

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    # ... (function remains the same as before)
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if not email:
            flash("Please enter your email.", "warning")
            return redirect(url_for("login")) 

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM users WHERE Email=%s", (email,))
                    user = cur.fetchone()
                    if user:
                        temp_password = secrets.token_urlsafe(8)
                        cur.execute("UPDATE users SET Password=%s WHERE Email=%s", (temp_password, email))
                        conn.commit()
                        flash(f"Your temporary password is: {temp_password} (Please login and change it)", "success")
                        return redirect(url_for("login"))
                    else:
                        flash("If the email is registered, a password reset link has been sent.", "success")
                        return redirect(url_for("login"))

        except (ValueError, ConnectionError, Exception) as e:
            flash(f"Password reset failed: Database error. {e}", "danger")

    return render_template("login.html") 

# -------------------------
# Dashboard Routes
# -------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    notifications = []
    latest_sensor = {}
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("SELECT DateTime, message FROM notifications ORDER BY DateTime DESC LIMIT 10")
                    notifications = cur.fetchall()
                except OperationalError:
                    print("NOTICE: 'notifications' table not found. Skipping notifications fetch.")
                    notifications = []

                cur.execute(
                    "SELECT DateTime, Temperature, Humidity, Ammonia, "
                    "CASE WHEN Light1 THEN 'ON' ELSE 'OFF' END AS Light1, "
                    "CASE WHEN Light2 THEN 'ON' ELSE 'OFF' END AS Light2, "
                    "CASE WHEN ExhaustFan THEN 'ON' ELSE 'OFF' END AS ExhaustFan "
                    "FROM sensordata ORDER BY DateTime DESC LIMIT 1"
                )
                latest_sensor = cur.fetchone()
    except (ValueError, ConnectionError, Exception) as e:
        print(f"Error fetching dashboard data: {e}")
        flash(f"Error loading dashboard data: {e}", "danger") 
        latest_sensor = None

    return render_template(
        "dashboard.html",
        image_files=list_shots(),
        notifications=notifications,
        data=latest_sensor
    )

# ... (Other dashboard routes remain the same) ...
@app.route("/main_dashboard")
@login_required 
def main_dashboard():
    return render_template("main-dashboard.html")

@app.route("/admin_dashboard")
@login_required 
def admin_dashboard():
    if session.get("user_role") != "admin":
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("admin-dashboard.html")

@app.route("/manage_users")
@login_required 
def manage_users():
    if session.get("user_role") != "admin":
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("manage-users.html")

@app.route("/report")
@login_required 
def report():
    return render_template("report.html")

# -------------------------
# API Endpoints
# -------------------------

# Utility function to fetch latest row from a specific table (same as before)
def fetch_latest_data(table_name, column_mappings=None):
    """Fetches the latest row from a specified table, handling BOOLEAN to string conversion."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                select_parts = []
                for db_col, api_col in column_mappings.items():
                    if 'light' in db_col.lower() or 'fan' in db_col.lower() or 'control' in db_col.lower() or 'food' in db_col.lower() or 'water' in db_col.lower() or 'conveyor' in db_col.lower() or 'uv' in db_col.lower() or 'sprinkle' in db_col.lower():
                         select_parts.append(f"CASE WHEN {db_col} THEN 'ON' ELSE 'OFF' END AS {api_col}")
                    else:
                         select_parts.append(f"{db_col} AS {api_col}")

                select_cols = ", ".join(select_parts)
                
                if not column_mappings:
                     select_cols = "*"

                cur.execute(f"SELECT {select_cols} FROM {table_name} ORDER BY DateTime DESC LIMIT 1")
                return cur.fetchone() or {}
    except OperationalError as oe:
        print(f"Operational Error in {table_name}: {oe}")
        return {"error": f"Table {table_name} not found or inaccessible."}
    except (ValueError, ConnectionError, Exception) as e:
        print(f"General Error in {table_name}: {e}")
        return {"error": f"Database connection or query failed: {str(e)}"}


@app.route("/get_full_sensor_data")
def get_full_sensor_data():
    all_data = {}

    all_data["environment"] = fetch_latest_data(
        "sensordata",
        {"Temperature": "Temp", "Humidity": "Hum", "Ammonia": "Amm", "Light1": "Light1", "Light2": "Light2", "ExhaustFan": "ExhaustFan", "DateTime": "DateTime"}
    )
    
    all_data["feed_water"] = fetch_latest_data(
        "sensordata1",
        {"Food": "FoodControl", "Water": "WaterControl", "DateTime": "DateTime"}
    )

    all_data["floor_uv"] = fetch_latest_data(
        "sensordata2",
        {"Conveyor": "ConveyorControl", "Sprinkle": "SprinkleControl", "UVLight": "UVControl", "DateTime": "DateTime"}
    )
    
    all_data["latest_weight"] = fetch_latest_data(
        "sensordata3",
        {"ChickNumber": "ChickNumber", "Weight": "Weight", "AverageWeight": "AvgWeight", "DateTime": "DateTime"}
    )
    
    all_data["levels"] = fetch_latest_data(
        "sensordata4",
        {"Water_Level": "WaterLevel", "Food_Level": "FoodLevel", "DateTime": "DateTime"}
    )

    if any(isinstance(data, dict) and 'error' in data for data in all_data.values()):
           return jsonify({"error": "Failed to fetch all sensor data", "details": all_data}), 500

    return jsonify(all_data)


# -------------------------
# NEW ROUTES TO FIX 404 ERRORS IN LOGS
# -------------------------

@app.route("/data")
def get_report_data():
    """Placeholder for the /data route causing 404 errors."""
    # Assuming the /data route is used to fetch bulk report data
    # We will return the same data as /get_all_data for now, or an empty array if not defined.
    print("WARNING: /data route hit. Using /get_all_data logic as placeholder.")
    return get_all_data()

@app.route("/sanitization")
def get_sanitization_status():
    """Placeholder for the /sanitization route causing 404 errors."""
    # This route likely fetches controls from sensordata2 (Conveyor, Sprinkle, UVLight)
    data = fetch_latest_data(
        "sensordata2",
        {"Conveyor": "ConveyorControl", "Sprinkle": "SprinkleControl", "UVLight": "UVControl", "DateTime": "DateTime"}
    )
    if 'error' in data:
        return jsonify(data), 500
    return jsonify(data or {"ConveyorControl": "N/A", "SprinkleControl": "N/A", "UVControl": "N/A"})


@app.route("/webcam")
def get_webcam_feed():
    """Placeholder for the /webcam route causing 404 errors."""
    # This route typically returns a stream or a list of images
    return jsonify({"image_list": [f"/static/shots/{f}" for f in list_shots()]})


# Retain /get_data and /get_all_data for backward compatibility
@app.route("/get_data")
def get_data():
    data = fetch_latest_data(
        "sensordata",
        {"Temperature": "Temp", "Humidity": "Hum", "Ammonia": "Amm", "Light1": "Light1", "Light2": "Light2", "ExhaustFan": "ExhaustFan"}
    )
    if 'error' in data:
        return jsonify(data), 500
    return jsonify(data or {"Temp": None, "Hum": None, "Light1": None, "Light2": None, "Amm": None, "ExhaustFan": None})


@app.route("/get_all_data")
def get_all_data():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DateTime, Temperature, Humidity, Ammonia, "
                    "CASE WHEN Light1 THEN 'ON' ELSE 'OFF' END AS Light1, "
                    "CASE WHEN Light2 THEN 'ON' ELSE 'OFF' END AS Light2, "
                    "CASE WHEN ExhaustFan THEN 'ON' ELSE 'OFF' END AS ExhaustFan "
                    "FROM sensordata ORDER BY DateTime DESC LIMIT 10"
                )
                rows = cur.fetchall()
        return jsonify(rows)
    except (ValueError, ConnectionError, Exception) as e:
        print(f"Error in get_all_data: {e}")
        return jsonify({"error": "Database connection or query failed", "detail": str(e)}), 500


@app.route("/get_all_notifications")
def get_all_notifications():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DateTime, COALESCE(message, 'N/A') AS message FROM notifications ORDER BY DateTime DESC LIMIT 50")
                rows = cur.fetchall()
        return jsonify(rows)
    except (ValueError, ConnectionError, OperationalError) as e:
        print(f"Error in get_all_notifications: {e}")
        return jsonify({"error": "Database connection or query failed", "detail": str(e)}), 500


@app.route("/insert_notifications", methods=["POST"])
def insert_notifications():
    payload = request.get_json() or {}
    items = payload.get("notifications") or payload.get("messages") or []
    if not items:
        return jsonify({"success": False, "message": "No notifications provided"}), 400
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for msg in items:
                    cur.execute("INSERT INTO notifications (message) VALUES (%s)", (msg,))
            conn.commit()
        return jsonify({"success": True, "inserted": len(items)})
    except (ValueError, ConnectionError, Exception) as e:
        print(f"Error in insert_notifications: {e}")
        return jsonify({"success": False, "message": f"Insertion failed due to database error: {e}"}), 500

# -------------------------
# Health Check
# -------------------------
@app.route("/health")
def health():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return jsonify({"status": "ok", "database": "connected"})
    except (ValueError, ConnectionError, Exception) as e:
        return jsonify({"status": "error", "database": f"connection failed: {e}"}), 500

# -------------------------
# Main Entry
# -------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)
