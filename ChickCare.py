from flask import Flask, render_template, jsonify, request, session, flash, url_for, redirect
import sqlite3
import os
from datetime import datetime, timedelta
import time

# -------------------------
# App config
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = "supersecretkey"  # change this in production!

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Use the filename you provided; sqlite works with any extension
DB_PATH = os.path.join(DATA_DIR, "test.sql")

# -------------------------
# DB helpers
# -------------------------
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create tables if they don't exist (simple schema adapted from your original)."""
    conn = get_db_connection()
    c = conn.cursor()
    # Users
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        Email TEXT,
        Username TEXT UNIQUE,
        Password TEXT
    )
    """)
    # Environment sensor table (sensordata)
    c.execute("""
    CREATE TABLE IF NOT EXISTS sensordata (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        DateTime TEXT DEFAULT (datetime('now')),
        Humidity REAL,
        Temperature REAL,
        Light1 TEXT,
        Light2 TEXT,
        Ammonia REAL,
        ExhaustFan TEXT
    )
    """)
    # Supplies (sensordata1)
    c.execute("""
    CREATE TABLE IF NOT EXISTS sensordata1 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        DateTime TEXT DEFAULT (datetime('now')),
        Food TEXT,
        Water TEXT
    )
    """)
    # Sanitization (sensordata2)
    c.execute("""
    CREATE TABLE IF NOT EXISTS sensordata2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        DateTime TEXT DEFAULT (datetime('now')),
        Conveyor TEXT,
        Sprinkle TEXT,
        UVLight TEXT
    )
    """)
    # Growth / weights (sensordata3)
    c.execute("""
    CREATE TABLE IF NOT EXISTS sensordata3 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        DateTime TEXT DEFAULT (datetime('now')),
        ChickNumber TEXT,
        Weight REAL,
        WeighingCount INTEGER,
        AverageWeight REAL
    )
    """)
    # Water/Food levels (sensordata4)
    c.execute("""
    CREATE TABLE IF NOT EXISTS sensordata4 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        DateTime TEXT DEFAULT (datetime('now')),
        Water_Level REAL,
        Food_Level REAL
    )
    """)
    # Notifications
    c.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        DateTime TEXT DEFAULT (datetime('now')),
        message TEXT
    )
    """)
    # Chick status
    c.execute("""
    CREATE TABLE IF NOT EXISTS chickstatus (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        DateTime TEXT DEFAULT (datetime('now')),
        ChickNumber TEXT,
        status TEXT
    )
    """)
    # Chick records (registration)
    c.execute("""
    CREATE TABLE IF NOT EXISTS chick_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ChickNumber TEXT UNIQUE,
        registration_date TEXT
    )
    """)
    conn.commit()
    conn.close()

# initialize DB at startup
init_db()

# -------------------------
# Auth: login / register
# -------------------------
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    err = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if not username or not password:
            err = "Please provide username and password."
        else:
            # Admin static login (same as your original)
            if username.lower() == "admin" and password == "admin":
                session["user_role"] = "admin"
                session["email"] = "admin@yourdomain.com"
                return redirect(url_for("dashboard"))

            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE Username = ? AND Password = ?", (username, password))
            user = cur.fetchone()
            conn.close()
            if user:
                session["user_role"] = "user"
                session["email"] = user["Email"]
                return redirect(url_for("dashboard"))
            else:
                err = "Invalid credentials."
    return render_template("login.html", error=err)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if not username or not password or not email:
            flash("Please fill all fields.", "warning")
            return redirect(url_for("register"))
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (Email, Username, Password) VALUES (?, ?, ?)",
                        (email, username, password))
            conn.commit()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already taken.", "danger")
        finally:
            conn.close()
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))

# -------------------------
# Dashboard + pages
# -------------------------
# list of images in static/shots (if present)
def list_shots():
    shots_folder = os.path.join(app.static_folder or "static", "shots")
    try:
        files = [f for f in os.listdir(shots_folder) if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif"))]
    except Exception:
        files = []
    return files

@app.route("/dashboard")
def dashboard():
    if "user_role" not in session:
        return redirect(url_for("login"))
    # get recent notifications and latest sensor row
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT DateTime, message FROM notifications ORDER BY DateTime DESC LIMIT 10")
    notifications = [dict(row) for row in cur.fetchall()]
    cur.execute("SELECT * FROM sensordata ORDER BY DateTime DESC LIMIT 1")
    latest_sensor = cur.fetchone()
    conn.close()
    return render_template("dashboard.html", image_files=list_shots(), notifications=notifications, data=(dict(latest_sensor) if latest_sensor else None))

# simple static routes for pages you used before (templates should exist)
@app.route("/main_dashboard")
def main_dashboard():
    return render_template("main-dashboard.html")

@app.route("/admin_dashboard")
def admin_dashboard():
    return render_template("admin-dashboard.html")

@app.route("/manage_users")
def manage_users():
    return render_template("manage-users.html")

@app.route("/report")
def report():
    return render_template("report.html")

# -------------------------
# API endpoints (read-only)
# -------------------------
@app.route("/get_image_list")
def get_image_list():
    return jsonify(list_shots())

@app.route("/get_data")
def get_data():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT Temperature AS Temp, Humidity AS Hum, Light1, Light2, Ammonia AS Amm, ExhaustFan FROM sensordata ORDER BY DateTime DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if row:
        return jsonify(dict(row))
    return jsonify({"error": "No data found"}), 404

@app.route("/get_all_data")
def get_all_data():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT DateTime, Temperature, Humidity, Light1, Light2, Ammonia, ExhaustFan FROM sensordata ORDER BY DateTime DESC LIMIT 10")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)

# generic endpoints for other tables (notifications, sensordata1..4, sensordata3...)
@app.route("/get_all_notifications")
def get_all_notifications():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT DateTime, message FROM notifications ORDER BY DateTime DESC LIMIT 50")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)

# Insert notifications (called from frontend)
@app.route("/insert_notifications", methods=["POST"])
def insert_notifications():
    payload = request.get_json() or {}
    items = payload.get("notifications") or payload.get("messages") or []
    if not items:
        return jsonify({"success": False, "message": "No notifications provided"}), 400
    conn = get_db_connection()
    cur = conn.cursor()
    for msg in items:
        cur.execute("INSERT INTO notifications (message) VALUES (?)", (msg,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "inserted": len(items)})

# Manage users (update / delete) simplified
@app.route("/update_user", methods=["POST"])
def update_user():
    data = request.get_json() or {}
    user_id = data.get("id")
    email = data.get("email")
    username = data.get("username")
    password = data.get("password")
    if not user_id:
        return jsonify({"success": False, "message": "id required"}), 400
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET Email=?, Username=?, Password=? WHERE id=?", (email, username, password, user_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/delete_user", methods=["POST"])
def delete_user():
    data = request.get_json() or {}
    user_id = data.get("id")
    if not user_id:
        return jsonify({"success": False, "message": "id required"}), 400
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# -------------------------
# Filtered / reports endpoint (simple)
# -------------------------
@app.route("/get_filtered_data")
def get_filtered_data():
    record_type = request.args.get("recordType", "notifications")
    from_date = request.args.get("fromDate")
    to_date = request.args.get("toDate")
    search = request.args.get("search")
    # map to table names
    table_map = {
        "notifications": "notifications",
        "supplies": "sensordata1",
        "environment": "sensordata",
        "growth": "sensordata3",
        "sanitization": "sensordata2"
    }
    table = table_map.get(record_type, "notifications")
    sql = f"SELECT * FROM {table}"
    params = []
    where = []
    if from_date and to_date:
        where.append("DateTime BETWEEN ? AND ?")
        params.extend([from_date + " 00:00:00", to_date + " 23:59:59"])
    if search:
        # naive search on message or default column
        where.append("message LIKE ?")
        params.append(f"%{search}%")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY DateTime DESC LIMIT 700"
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500
    conn.close()
    return jsonify(rows)

# -------------------------
# Health & misc
# -------------------------
@app.route("/health")
def health():
    return jsonify({"status": "ok"})

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    # dev server; on Fly.io it'll be started inside Docker (port 8080)
    app.run(host="0.0.0.0", port=8080, debug=True)
