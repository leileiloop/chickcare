from flask import Flask, render_template, jsonify, request, session, flash, url_for, redirect
import os
import psycopg2
import psycopg2.extras
import requests

# -------------------------
# App Config
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")  # override in Render

# -------------------------
# PostgreSQL DB Config
# -------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")  # Set this in Render env vars

def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set in environment variables.")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn

def get_db_cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# -------------------------
# Initialize DB Tables
# -------------------------
def init_db():
    conn = cur = None
    try:
        conn = get_db_connection()
        cur = get_db_cursor(conn)

        # Users
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            Email TEXT,
            Username TEXT UNIQUE,
            Password TEXT
        )
        """)

        # Environment sensor table
        cur.execute("""
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
        """)

        # Supplies
        cur.execute("""
        CREATE TABLE IF NOT EXISTS sensordata1 (
            id SERIAL PRIMARY KEY,
            DateTime TIMESTAMP DEFAULT NOW(),
            Food TEXT,
            Water TEXT
        )
        """)

        # Sanitization
        cur.execute("""
        CREATE TABLE IF NOT EXISTS sensordata2 (
            id SERIAL PRIMARY KEY,
            DateTime TIMESTAMP DEFAULT NOW(),
            Conveyor TEXT,
            Sprinkle TEXT,
            UVLight TEXT
        )
        """)

        # Growth / Weights
        cur.execute("""
        CREATE TABLE IF NOT EXISTS sensordata3 (
            id SERIAL PRIMARY KEY,
            DateTime TIMESTAMP DEFAULT NOW(),
            ChickNumber TEXT,
            Weight REAL,
            WeighingCount INTEGER,
            AverageWeight REAL
        )
        """)

        # Water/Food levels
        cur.execute("""
        CREATE TABLE IF NOT EXISTS sensordata4 (
            id SERIAL PRIMARY KEY,
            DateTime TIMESTAMP DEFAULT NOW(),
            Water_Level REAL,
            Food_Level REAL
        )
        """)

        # Notifications
        cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            DateTime TIMESTAMP DEFAULT NOW(),
            message TEXT
        )
        """)

        # Chick status
        cur.execute("""
        CREATE TABLE IF NOT EXISTS chickstatus (
            id SERIAL PRIMARY KEY,
            DateTime TIMESTAMP DEFAULT NOW(),
            ChickNumber TEXT,
            status TEXT
        )
        """)

        # Chick records
        cur.execute("""
        CREATE TABLE IF NOT EXISTS chick_records (
            id SERIAL PRIMARY KEY,
            ChickNumber TEXT UNIQUE,
            registration_date TIMESTAMP DEFAULT NOW()
        )
        """)

        print("Tables initialized successfully.")

    except Exception as e:
        print(f"DB initialization failed: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

# -------------------------
# Load GitHub SQL
# -------------------------
GITHUB_RAW_URL = "https://raw.githubusercontent.com/leileiloop/chickcare/main/test.sql"

def run_github_sql():
    conn = cur = None
    try:
        conn = get_db_connection()
        cur = get_db_cursor(conn)

        response = requests.get(GITHUB_RAW_URL)
        response.raise_for_status()
        sql_text = response.text

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
    finally:
        if cur: cur.close()
        if conn: conn.close()

# -------------------------
# Initialize DB + GitHub SQL
# -------------------------
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
            # Admin static login
            if username.lower() == "admin" and password == "admin":
                session["user_role"] = "admin"
                session["email"] = "admin@domain.com"
                return redirect(url_for("dashboard"))

            conn = cur = None
            try:
                conn = get_db_connection()
                cur = get_db_cursor(conn)
                cur.execute("SELECT * FROM users WHERE Username=%s AND Password=%s", (username, password))
                user = cur.fetchone()
            except Exception as e:
                error = f"DB error: {e}"
                user = None
            finally:
                if cur: cur.close()
                if conn: conn.close()

            if user:
                session["user_role"] = "user"
                session["email"] = user["Email"]
                return redirect(url_for("dashboard"))
            else:
                error = error or "Invalid credentials."

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

        conn = cur = None
        try:
            conn = get_db_connection()
            cur = get_db_cursor(conn)
            cur.execute("INSERT INTO users (Email, Username, Password) VALUES (%s,%s,%s)", (email, username, password))
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except psycopg2.errors.UniqueViolation:
            flash("Username already taken.", "danger")
        except Exception as e:
            flash(f"DB error: {e}", "danger")
        finally:
            if cur: cur.close()
            if conn: conn.close()

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
    conn = cur = None
    try:
        conn = get_db_connection()
        cur = get_db_cursor(conn)
        cur.execute("SELECT DateTime, message FROM notifications ORDER BY DateTime DESC LIMIT 10")
        notifications = [dict(row) for row in cur.fetchall()]

        cur.execute("SELECT * FROM sensordata ORDER BY DateTime DESC LIMIT 1")
        latest_sensor = cur.fetchone()
    except Exception as e:
        print(f"Dashboard DB error: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

    return render_template(
        "dashboard.html",
        image_files=list_shots(),
        notifications=notifications,
        data=dict(latest_sensor) if latest_sensor else None
    )

# -------------------------
# Health
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
