import os
import secrets
import functools
import psycopg
from psycopg.rows import dict_row
from psycopg.errors import UniqueViolation, OperationalError
from flask import Flask, render_template, jsonify, request, session, flash, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# -------------------------
# App Configuration
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# -------------------------
# PostgreSQL Configuration
# -------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    """
    Connect to PostgreSQL with SSL.
    """
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is not set.")

    conn_str = DATABASE_URL

    if conn_str.startswith("DATABASE_URL="):
        conn_str = conn_str.split("=", 1)[1]

    if conn_str.startswith("postgres://"):
        conn_str = conn_str.replace("postgres://", "postgresql://", 1)

    if "sslmode" not in conn_str:
        conn_str += "&sslmode=require" if "?" in conn_str else "?sslmode=require"

    try:
        return psycopg.connect(conn_str, row_factory=dict_row)
    except OperationalError as e:
        raise ConnectionError(f"Database connection failed: {e}")

# -------------------------
# Utility Functions & Decorators
# -------------------------
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if "user_role" not in session:
            flash("You must log in first.", "warning")
            return redirect(url_for("login"))
        return view(**kwargs)
    return wrapped_view

def list_shots():
    """Return list of image files in static/shots"""
    shots_dir = os.path.join(app.static_folder, "shots")
    if os.path.exists(shots_dir):
        return [f for f in os.listdir(shots_dir) if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif"))]
    return []

def fetch_latest_data(table_name, column_mappings=None):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                select_cols = "*"
                if column_mappings:
                    parts = []
                    for db_col, api_col in column_mappings.items():
                        if any(k in db_col.lower() for k in ['light', 'fan', 'control', 'food', 'water', 'conveyor', 'uv', 'sprinkle']):
                            parts.append(f"CASE WHEN UPPER({db_col}::text)='ON' THEN 'ON' ELSE 'OFF' END AS {api_col}")
                        else:
                            parts.append(f"{db_col} AS {api_col}")
                    select_cols = ", ".join(parts)
                cur.execute(f"SELECT {select_cols} FROM {table_name} ORDER BY DateTime DESC LIMIT 1")
                return cur.fetchone() or {}
    except Exception as e:
        print(f"Error fetching latest data from {table_name}: {e}")
        return {"error": str(e)}

def fetch_history_data(table_name, column_mappings=None, limit=50):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                select_cols = "*"
                if column_mappings:
                    parts = []
                    for db_col, api_col in column_mappings.items():
                        if any(k in db_col.lower() for k in ['conveyor', 'uv', 'sprinkle']):
                            parts.append(f"CASE WHEN UPPER({db_col}::text)='ON' THEN 'ON' ELSE 'OFF' END AS {api_col}")
                        else:
                            parts.append(f"{db_col} AS {api_col}")
                    select_cols = ", ".join(parts)
                cur.execute(f"SELECT {select_cols} FROM {table_name} ORDER BY DateTime DESC LIMIT {limit}")
                return cur.fetchall()
    except Exception as e:
        print(f"Error fetching history from {table_name}: {e}")
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
            error = "Provide username and password."
        elif username.lower() == "admin" and password == "admin":
            session.clear()
            session["user_role"] = "admin"
            session["email"] = "admin@domain.com"
            flash("Admin logged in.", "success")
            return redirect(url_for("dashboard"))
        else:
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT * FROM users WHERE Username=%s", (username,))
                        user = cur.fetchone()
                        if user and check_password_hash(user["Password"], password):
                            session.clear()
                            session["user_role"] = "user"
                            session["email"] = user["Email"]
                            flash("Login successful.", "success")
                            return redirect(url_for("dashboard"))
                        else:
                            error = "Invalid credentials."
            except Exception as e:
                error = f"Login failed: {e}"
                print(f"LOGIN ERROR: {e}")

    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not email or not username or not password:
            flash("Fill all fields.", "warning")
            return redirect(url_for("register"))

        hashed = generate_password_hash(password)
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO users (Email, Username, Password) VALUES (%s, %s, %s)", (email, username, hashed))
                conn.commit()
            flash("Registration successful. Login now.", "success")
            return redirect(url_for("login"))
        except UniqueViolation:
            flash("Username or email exists.", "danger")
        except Exception as e:
            flash(f"Registration error: {e}", "danger")
            print(f"REGISTER ERROR: {e}")

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
            flash("Enter your email.", "warning")
            return redirect(url_for("forgot_password"))

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM users WHERE Email=%s", (email,))
                    user = cur.fetchone()
                    if user:
                        temp_pass = secrets.token_urlsafe(8)
                        hashed = generate_password_hash(temp_pass)
                        cur.execute("UPDATE users SET Password=%s WHERE Email=%s", (hashed, email))
                        conn.commit()
                        flash(f"Temporary password: {temp_pass}", "success")  # Replace with email in real app
                        return redirect(url_for("login"))
                    else:
                        flash("If registered, password reset sent.", "success")
                        return redirect(url_for("login"))
        except Exception as e:
            flash(f"Password reset failed: {e}", "danger")
            return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")

# -------------------------
# Dashboard Routes
# -------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    notifications = fetch_history_data("notifications", {"DateTime": "DateTime", "message": "message"}, 10)
    latest_sensor = fetch_latest_data("sensordata", {
        "Temperature": "Temp", "Humidity": "Hum", "Ammonia": "Amm",
        "Light1": "Light1", "Light2": "Light2", "ExhaustFan": "ExhaustFan",
        "DateTime": "DateTime"
    })
    return render_template("dashboard.html", image_files=list_shots(), notifications=notifications, data=latest_sensor)

@app.route("/main_dashboard")
@login_required
def main_dashboard():
    return render_template("main-dashboard.html")

@app.route("/admin_dashboard")
@login_required
def admin_dashboard():
    if session.get("user_role") != "admin":
        flash("Admin only.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("admin-dashboard.html")

@app.route("/manage_users")
@login_required
def manage_users():
    if session.get("user_role") != "admin":
        flash("Admin only.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("manage-users.html")

@app.route("/report")
@login_required
def report():
    return render_template("report.html")

@app.route("/sanitization")
@login_required
def sanitization_page():
    return render_template("sanitization.html")

# -------------------------
# API Endpoints
# -------------------------
@app.route("/api/sanitization/status")
@login_required
def get_sanitization_status_api():
    data = fetch_latest_data("sensordata2", {"Conveyor": "conveyor", "Sprinkle": "sprinkle", "UVLight": "uvclight"})
    if "error" in data: return jsonify(data), 500
    return jsonify({k: data.get(k) == "ON" for k in ["conveyor", "sprinkle", "uvclight"]})

@app.route("/api/sanitization/history")
@login_required
def get_sanitization_history_api():
    history = fetch_history_data("sensordata2", {"DateTime":"DateTime","Conveyor":"Conveyor","Sprinkle":"Sprinkle","UVLight":"UVLight"}, limit=50)
    return jsonify(history)

@app.route("/api/sanitization/stop", methods=["POST"])
@login_required
def set_sanitization_stop_api():
    payload = request.get_json() or {}
    device = payload.get("device")
    if device not in ["conveyor", "sprinkle", "uvclight"]:
        return jsonify({"success": False, "message": f"Invalid device: {device}"}), 400

    db_col = {"conveyor":"Conveyor","sprinkle":"Sprinkle","uvclight":"UVLight"}[device]

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT Conveyor, Sprinkle, UVLight FROM sensordata2 ORDER BY DateTime DESC LIMIT 1")
                latest = cur.fetchone() or {"Conveyor":"OFF","Sprinkle":"OFF","UVLight":"OFF"}
                latest[db_col] = "OFF"
                cur.execute("INSERT INTO sensordata2 (Conveyor,Sprinkle,UVLight) VALUES (%s,%s,%s)",
                            (latest["Conveyor"], latest["Sprinkle"], latest["UVLight"]))
            conn.commit()
        return jsonify({"success": True, "message": f"{device.capitalize()} stopped."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/get_full_sensor_data")
def get_full_sensor_data():
    data = {
        "environment": fetch_latest_data("sensordata", {"Temperature":"Temp","Humidity":"Hum","Ammonia":"Amm","Light1":"Light1","Light2":"Light2","ExhaustFan":"ExhaustFan","DateTime":"DateTime"}),
        "feed_water": fetch_latest_data("sensordata1", {"Food":"FoodControl","Water":"WaterControl","DateTime":"DateTime"}),
        "floor_uv": fetch_latest_data("sensordata2", {"Conveyor":"ConveyorControl","Sprinkle":"SprinkleControl","UVLight":"UVControl","DateTime":"DateTime"}),
        "latest_weight": fetch_latest_data("sensordata3", {"ChickNumber":"ChickNumber","Weight":"Weight","AverageWeight":"AvgWeight","DateTime":"DateTime"}),
        "levels": fetch_latest_data("sensordata4", {"Water_Level":"WaterLevel","Food_Level":"FoodLevel","DateTime":"DateTime"})
    }
    if any("error" in d for d in data.values()):
        return jsonify({"error":"Failed to fetch all sensor data", "details": data}), 500
    return jsonify(data)

@app.route("/get_all_data")
def get_all_data():
    rows = fetch_history_data("sensordata", {"DateTime":"DateTime","Temperature":"Temp","Humidity":"Hum","Ammonia":"Amm","Light1":"Light1","Light2":"Light2","ExhaustFan":"ExhaustFan"}, limit=10)
    return jsonify(rows)

@app.route("/get_all_notifications")
def get_all_notifications():
    rows = fetch_history_data("notifications", {"DateTime":"DateTime","message":"message"}, limit=50)
    return jsonify(rows)

@app.route("/insert_notifications", methods=["POST"])
def insert_notifications():
    items = (request.get_json() or {}).get("notifications", [])
    if not items: return jsonify({"success": False, "message": "No notifications provided"}), 400
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for msg in items:
                    cur.execute("INSERT INTO notifications (message) VALUES (%s)", (msg,))
            conn.commit()
        return jsonify({"success": True, "inserted": len(items)})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/webcam")
def get_webcam_feed():
    return jsonify({"image_list": [f"/static/shots/{f}" for f in list_shots()]})

@app.route("/health")
def health():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return jsonify({"status":"ok","database":"connected"})
    except Exception as e:
        return jsonify({"status":"error","database":str(e)}), 500

# -------------------------
# Main Entry
# -------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)
