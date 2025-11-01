# ChickCare.py
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import psycopg
from psycopg.rows import dict_row
import requests

# -------------------------
# App Config
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")  # override in Render

# -------------------------
# PostgreSQL DB Config
# -------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set in environment variables.")
    return psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row)

# -------------------------
# Initialize DB Tables
# -------------------------
def init_db():
    commands = [
        """CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            Email TEXT,
            Username TEXT UNIQUE,
            Password TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS sensordata (
            id SERIAL PRIMARY KEY,
            DateTime TIMESTAMP DEFAULT NOW(),
            Humidity REAL,
            Temperature REAL,
            Light1 TEXT,
            Light2 TEXT,
            Ammonia REAL,
            ExhaustFan TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS sensordata1 (
            id SERIAL PRIMARY KEY,
            DateTime TIMESTAMP DEFAULT NOW(),
            Food TEXT,
            Water TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS sensordata2 (
            id SERIAL PRIMARY KEY,
            DateTime TIMESTAMP DEFAULT NOW(),
            Conveyor TEXT,
            Sprinkle TEXT,
            UVLight TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS sensordata3 (
            id SERIAL PRIMARY KEY,
            DateTime TIMESTAMP DEFAULT NOW(),
            ChickNumber TEXT,
            Weight REAL,
            WeighingCount INTEGER,
            AverageWeight REAL
        )""",
        """CREATE TABLE IF NOT EXISTS sensordata4 (
            id SERIAL PRIMARY KEY,
            DateTime TIMESTAMP DEFAULT NOW(),
            Water_Level REAL,
            Food_Level REAL
        )""",
        """CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            DateTime TIMESTAMP DEFAULT NOW(),
            message TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS chickstatus (
            id SERIAL PRIMARY KEY,
            DateTime TIMESTAMP DEFAULT NOW(),
            ChickNumber TEXT,
            status TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS chick_records (
            id SERIAL PRIMARY KEY,
            ChickNumber TEXT UNIQUE,
            registration_date TIMESTAMP DEFAULT NOW()
        )"""
    ]
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for cmd in commands:
                    cur.execute(cmd)
        print("Tables initialized successfully.")
    except Exception as e:
        print(f"DB initialization failed: {e}")

# -------------------------
# Run GitHub SQL
# -------------------------
GITHUB_RAW_URL = "https://raw.githubusercontent.com/leileiloop/chickcare/main/test.sql"

def run_github_sql():
    try:
        response = requests.get(GITHUB_RAW_URL)
        response.raise_for_status()
        sql_text = response.text

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for cmd in sql_text.split(";"):
                    cmd = cmd.strip()
                    if cmd:
                        try:
                            cur.execute(cmd)
                        except Exception as e:
                            print("Skipping SQL command error:", e)
        print("GitHub SQL executed successfully!")
    except Exception as e:
        print("Error running GitHub SQL:", e)

# Initialize DB and run GitHub SQL
init_db()
run_github_sql()

# -------------------------
# Auth Routes
# -------------------------
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            error = "Please provide username and password."
        else:
            if username.lower() == "admin" and password == "admin":
                session["user_role"] = "admin"
                session["email"] = "admin@domain.com"
                return redirect(url_for("dashboard"))

            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT * FROM users WHERE Username=%s AND Password=%s",
                            (username, password)
                        )
                        user = cur.fetchone()
                        if user:
                            session["user_role"] = "user"
                            session["email"] = user["Email"]
                            return redirect(url_for("dashboard"))
                        else:
                            error = "Invalid credentials."
            except Exception as e:
                error = f"DB error: {e}"

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
                        "INSERT INTO users (Email, Username, Password) VALUES (%s,%s,%s)",
                        (email, username, password)
                    )
                    flash("Registration successful. Please login.", "success")
                    return redirect(url_for("login"))
        except psycopg.errors.UniqueViolation:
            flash("Username already taken.", "danger")
        except Exception as e:
            flash(f"DB error: {e}", "danger")

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))

# -------------------------
# Dashboard
# -------------------------
def list_shots():
    shots_folder = os.path.join(app.static_folder, "shots")
    try:
        return [f for f in os.listdir(shots_folder) if f.lower().endswith((".jpg",".jpeg",".png",".gif"))]
    except Exception:
        return []

@app.route("/dashboard")
def dashboard():
    if "user_role" not in session:
        return redirect(url_for("login"))

    notifications = []
    latest_sensor = None
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DateTime, message FROM notifications ORDER BY DateTime DESC LIMIT 10")
                notifications = [dict(row) for row in cur.fetchall()]

                cur.execute("SELECT * FROM sensordata ORDER BY DateTime DESC LIMIT 1")
                latest_sensor = cur.fetchone()
    except Exception as e:
        print(f"Dashboard DB error: {e}")

    return render_template(
        "dashboard.html",
        image_files=list_shots(),
        notifications=notifications,
        data=dict(latest_sensor) if latest_sensor else None
    )

# -------------------------
# Health Check
# -------------------------
@app.route("/health")
def health():
    return jsonify({"status": "ok"})

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
