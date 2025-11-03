from flask import Flask, render_template, jsonify, request, session, flash, redirect, url_for
import psycopg
from psycopg.rows import dict_row
from psycopg.errors import UniqueViolation, OperationalError
from werkzeug.security import generate_password_hash, check_password_hash
import os
import secrets
import functools # ADDED: Required for the @login_required decorator

# -------------------------
# App Configuration
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey") # Change in production

# -------------------------
# PostgreSQL Configuration
# -------------------------
# CRITICAL: For deployment on Render, the DATABASE_URL environment variable MUST be set
# to the External Database URL of your PostgreSQL service. 
DATABASE_URL = os.environ.get("DATABASE_URL") 

def get_db_connection():
    """Connect to PostgreSQL with SSL. Raises a clear error if DATABASE_URL is not set or connection fails."""
    if not DATABASE_URL:
        # This provides a clear error instead of the ambiguous 'NoneType' crash.
        raise ValueError("DATABASE_URL environment variable is not set. Cannot establish database connection.")
    
    # Ensure sslmode="require" is used, which is mandatory for Render PostgreSQL.
    try:
        # FIX: Explicitly use conninfo=DATABASE_URL to ensure psycopg treats it as the connection string.
        return psycopg.connect(conninfo=DATABASE_URL, row_factory=dict_row, sslmode="require")
    except OperationalError as e:
        # Catch specific psycopg connection errors (like wrong URL, host unreachable)
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
        elif username.lower() == "admin" and password == "admin":
            session["user_role"] = "admin"
            session["email"] = "admin@yourdomain.com"
            return redirect(url_for("dashboard"))
        else:
            try:
                # Connection attempt happens here ⬇️
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT * FROM users WHERE Username=%s", (username,))
                        user = cur.fetchone()
                        if user and check_password_hash(user["Password"], password):
                            session["user_role"] = "user"
                            session["email"] = user["Email"]
                            return redirect(url_for("dashboard"))
                        error = "Invalid credentials."
            except (ValueError, ConnectionError, Exception) as e:
                # Catch configuration or connection errors and display them
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

        hashed_password = generate_password_hash(password)
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO users (Email, Username, Password) VALUES (%s, %s, %s)",
                        (email, username, hashed_password)
                    )
                conn.commit()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except UniqueViolation:
            flash("Username already taken.", "danger")
        except (ValueError, ConnectionError, Exception) as e:
            # Added ConnectionError check here for more granular feedback
            flash(f"Registration failed: {e}", "danger")

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if not email:
            flash("Please enter your email.", "warning")
            return redirect(url_for("forgot_password"))

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM users WHERE Email=%s", (email,))
                    user = cur.fetchone()
                    if user:
                        temp_password = secrets.token_urlsafe(8)
                        hashed_temp = generate_password_hash(temp_password)
                        cur.execute("UPDATE users SET Password=%s WHERE Email=%s", (hashed_temp, email))
                        conn.commit()
                        # NOTE: In a real app, you would send this via email.
                        flash(f"Your temporary password is: {temp_password}", "success")
                        return redirect(url_for("login"))
                    else:
                        flash("Email not found.", "danger")
        except (ValueError, ConnectionError, Exception) as e:
            # Used the general exception handling that was already defined to catch the connection errors here too.
            flash(f"Password reset failed: {e}", "danger")

    return render_template("forgot_password.html")

# -------------------------
# Dashboard Routes
# -------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    if "user_role" not in session:
        return redirect(url_for("login"))

    notifications = []
    latest_sensor = {}
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Attempt to select from notifications table (assuming you created it)
                try:
                    cur.execute("SELECT DateTime, message FROM notifications ORDER BY DateTime DESC LIMIT 10")
                    notifications = cur.fetchall()
                except OperationalError:
                    print("NOTICE: 'notifications' table not found. Skipping notifications fetch.")
                    notifications = []

                cur.execute("SELECT * FROM sensordata ORDER BY DateTime DESC LIMIT 1")
                latest_sensor = cur.fetchone()
    except (ValueError, ConnectionError, Exception) as e:
        print(f"Error fetching dashboard data: {e}")
        flash(f"Error loading dashboard data: {e}", "danger") # Added flash message for UI feedback
        # Application continues even if data fetching failed

    return render_template(
        "dashboard.html",
        image_files=list_shots(),
        notifications=notifications,
        data=latest_sensor
    )

@app.route("/main_dashboard")
@login_required # Route protected
def main_dashboard():
    return render_template("main-dashboard.html")

@app.route("/admin_dashboard")
@login_required # Route protected
def admin_dashboard():
    # ADDED: Security check for admin role
    if session.get("user_role") != "admin":
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("admin-dashboard.html")

@app.route("/manage_users")
@login_required # Route protected
def manage_users():
    # ADDED: Security check for admin role
    if session.get("user_role") != "admin":
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("manage-users.html")

@app.route("/report")
@login_required # Route protected
def report():
    return render_template("report.html")

# -------------------------
# API Endpoints
# -------------------------
@app.route("/get_image_list")
def get_image_list():
    return jsonify(list_shots())

@app.route("/get_data")
def get_data():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT Temperature AS Temp, Humidity AS Hum, Light1, Light2, Ammonia AS Amm, ExhaustFan "
                    "FROM sensordata ORDER BY DateTime DESC LIMIT 1"
                )
                row = cur.fetchone()
        return jsonify(row or {"Temp": None, "Hum": None, "Light1": None, "Light2": None, "Amm": None, "ExhaustFan": None})
    except (ValueError, ConnectionError, Exception) as e:
        print(f"Error in get_data: {e}")
        return jsonify({"error": "Database connection or query failed", "detail": str(e)}), 500


@app.route("/get_all_data")
def get_all_data():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DateTime, Temperature, Humidity, Light1, Light2, Ammonia, ExhaustFan "
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
                cur.execute("SELECT DateTime, message FROM notifications ORDER BY DateTime DESC LIMIT 50")
                rows = cur.fetchall()
        return jsonify(rows)
    except (ValueError, ConnectionError, OperationalError) as e: # Catch OperationalError for missing table
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
                    # Assuming 'notifications' table has a 'message' column and a default for 'DateTime'
                    cur.execute("INSERT INTO notifications (message) VALUES (%s)", (msg,))
            conn.commit()
        return jsonify({"success": True, "inserted": len(items)})
    except (ValueError, ConnectionError, Exception) as e:
        print(f"Error in insert_notifications: {e}")
        # Return 500 Internal Server Error if the table is missing or connection fails
        return jsonify({"success": False, "message": f"Insertion failed due to database error: {e}"}), 500

# -------------------------
# Health Check
# -------------------------
@app.route("/health")
def health():
    # Test database connection for a proper health check
    try:
        with get_db_connection() as conn:
            # Simple query to check if the connection is alive
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
