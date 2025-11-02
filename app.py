from flask import Flask, render_template, jsonify, request, session, flash, redirect, url_for
import os
import psycopg2
import psycopg2.extras

# -------------------------
# App Configuration
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecretkey")  # Change in production

# -------------------------
# PostgreSQL Configuration
# -------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")  # Must be set in Render environment

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)

# -------------------------
# Initialize Database Tables
# -------------------------
def init_db():
    table_queries = {
        "users": """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                Email TEXT,
                Username TEXT UNIQUE,
                Password TEXT
            )
        """,
        "sensordata": """
            CREATE TABLE IF NOT EXISTS sensordata (
                id SERIAL PRIMARY KEY,
                DateTime TIMESTAMP DEFAULT NOW(),
                Humidity REAL,
                Temperature REAL,
                Light1 TEXT,
                Light2 TEXT,
                Ammonia REAL,
                ExhaustFan TEXT
            )
        """,
        "sensordata1": """
            CREATE TABLE IF NOT EXISTS sensordata1 (
                id SERIAL PRIMARY KEY,
                DateTime TIMESTAMP DEFAULT NOW(),
                Food TEXT,
                Water TEXT
            )
        """,
        "sensordata2": """
            CREATE TABLE IF NOT EXISTS sensordata2 (
                id SERIAL PRIMARY KEY,
                DateTime TIMESTAMP DEFAULT NOW(),
                Conveyor TEXT,
                Sprinkle TEXT,
                UVLight TEXT
            )
        """,
        "sensordata3": """
            CREATE TABLE IF NOT EXISTS sensordata3 (
                id SERIAL PRIMARY KEY,
                DateTime TIMESTAMP DEFAULT NOW(),
                ChickNumber TEXT,
                Weight REAL,
                WeighingCount INTEGER,
                AverageWeight REAL
            )
        """,
        "sensordata4": """
            CREATE TABLE IF NOT EXISTS sensordata4 (
                id SERIAL PRIMARY KEY,
                DateTime TIMESTAMP DEFAULT NOW(),
                Water_Level REAL,
                Food_Level REAL
            )
        """,
        "notifications": """
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                DateTime TIMESTAMP DEFAULT NOW(),
                message TEXT
            )
        """,
        "chickstatus": """
            CREATE TABLE IF NOT EXISTS chickstatus (
                id SERIAL PRIMARY KEY,
                DateTime TIMESTAMP DEFAULT NOW(),
                ChickNumber TEXT,
                status TEXT
            )
        """,
        "chick_records": """
            CREATE TABLE IF NOT EXISTS chick_records (
                id SERIAL PRIMARY KEY,
                ChickNumber TEXT UNIQUE,
                registration_date TIMESTAMP DEFAULT NOW()
            )
        """
    }

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for query in table_queries.values():
                cur.execute(query)
    print("Database initialized.")

init_db()

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
            session.update({"user_role": "admin", "email": "admin@yourdomain.com"})
            return redirect(url_for("dashboard"))
        else:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT * FROM users WHERE Username=%s AND Password=%s",
                        (username, password)
                    )
                    user = cur.fetchone()
            if user:
                session.update({"user_role": "user", "email": user["Email"]})
                return redirect(url_for("dashboard"))
            error = "Invalid credentials."
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

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO users (Email, Username, Password) VALUES (%s, %s, %s)",
                        (email, username, password)
                    )
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except psycopg2.errors.UniqueViolation:
            flash("Username already taken.", "danger")
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))

# -------------------------
# Utility Functions
# -------------------------
def list_shots():
    shots_dir = os.path.join(app.static_folder, "shots")
    if os.path.exists(shots_dir):
        return [f for f in os.listdir(shots_dir) if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif"))]
    return []

# -------------------------
# Dashboard Routes
# -------------------------
@app.route("/dashboard")
def dashboard():
    if "user_role" not in session:
        return redirect(url_for("login"))

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DateTime, message FROM notifications ORDER BY DateTime DESC LIMIT 10")
            notifications = [dict(r) for r in cur.fetchall()]

            cur.execute("SELECT * FROM sensordata ORDER BY DateTime DESC LIMIT 1")
            latest_sensor = cur.fetchone()

    return render_template(
        "dashboard.html",
        image_files=list_shots(),
        notifications=notifications,
        data=dict(latest_sensor) if latest_sensor else None
    )

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
# API Endpoints
# -------------------------
@app.route("/get_image_list")
def get_image_list():
    return jsonify(list_shots())

@app.route("/get_data")
def get_data():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT Temperature AS Temp, Humidity AS Hum, Light1, Light2, Ammonia AS Amm, ExhaustFan "
                "FROM sensordata ORDER BY DateTime DESC LIMIT 1"
            )
            row = cur.fetchone()
    return jsonify(dict(row)) if row else jsonify({"error": "No data found"}), 404

@app.route("/get_all_data")
def get_all_data():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DateTime, Temperature, Humidity, Light1, Light2, Ammonia, ExhaustFan "
                "FROM sensordata ORDER BY DateTime DESC LIMIT 10"
            )
            rows = [dict(r) for r in cur.fetchall()]
    return jsonify(rows)

@app.route("/get_all_notifications")
def get_all_notifications():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DateTime, message FROM notifications ORDER BY DateTime DESC LIMIT 50")
            rows = [dict(r) for r in cur.fetchall()]
    return jsonify(rows)

@app.route("/insert_notifications", methods=["POST"])
def insert_notifications():
    payload = request.get_json() or {}
    items = payload.get("notifications") or payload.get("messages") or []
    if not items:
        return jsonify({"success": False, "message": "No notifications provided"}), 400
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for msg in items:
                cur.execute("INSERT INTO notifications (message) VALUES (%s)", (msg,))
    return jsonify({"success": True, "inserted": len(items)})

# -------------------------
# Health Check
# -------------------------
@app.route("/health")
def health():
    return jsonify({"status": "ok"})

# -------------------------
# Main Entry
# -------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)
