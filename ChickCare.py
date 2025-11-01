from flask import Flask, render_template, jsonify, request, session, flash, url_for, redirect
import os
import psycopg  # psycopg3, compatible with Python 3.13
import requests

# -------------------------
# App Configuration
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")  # override in Render

# -------------------------
# Database Configuration
# -------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is not set.")
    conn = psycopg.connect(DATABASE_URL, autocommit=True, sslmode='require')
    return conn

def get_db_cursor(conn):
    return conn.cursor(row_factory=psycopg.rows.dict_row)

# -------------------------
# Initialize Database
# -------------------------
def init_db():
    if not DATABASE_URL:
        print("Skipping DB initialization: DATABASE_URL not set.")
        return

    conn = cur = None
    try:
        conn = get_db_connection()
        cur = get_db_cursor(conn)

        # Users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                Email TEXT,
                Username TEXT UNIQUE,
                Password TEXT
            )
        """)

        # Sensor tables
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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sensordata1 (
                id SERIAL PRIMARY KEY,
                DateTime TIMESTAMP DEFAULT NOW(),
                Food TEXT,
                Water TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sensordata2 (
                id SERIAL PRIMARY KEY,
                DateTime TIMESTAMP DEFAULT NOW(),
                Conveyor TEXT,
                Sprinkle TEXT,
                UVLight TEXT
            )
        """)
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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sensordata4 (
                id SERIAL PRIMARY KEY,
                DateTime TIMESTAMP DEFAULT NOW(),
                Water_Level REAL,
                Food_Level REAL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                DateTime TIMESTAMP DEFAULT NOW(),
                message TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chickstatus (
                id SERIAL PRIMARY KEY,
                DateTime TIMESTAMP DEFAULT NOW(),
                ChickNumber TEXT,
                status TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chick_records (
                id SERIAL PRIMARY KEY,
                ChickNumber TEXT UNIQUE,
                registration_date TIMESTAMP DEFAULT NOW()
            )
        """)

        print("Database initialized successfully.")

    except Exception as e:
        print(f"DB initialization failed: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

# -------------------------
# Run SQL from GitHub
# -------------------------
GITHUB_RAW_URL = "https://raw.githubusercontent.com/<username>/<repo>/main/test.sql"  # replace <username>/<repo>

def run_github_sql():
    if not DATABASE_URL:
        print("DATABASE_URL not set, skipping SQL import.")
        return

    conn = cur = None
    try:
        conn = get_db_connection()
        cur = get_db_cursor(conn)

        response = requests.get(GITHUB_RAW_URL)
        response.raise_for_status()
        sql_text = response.text

        # Execute each command separately
        for command in sql_text.split(";"):
            cmd = command.strip()
            if cmd:
                try:
                    cur.execute(cmd)
                except Exception as e:
                    print("Skipping command error:", e)

        print("SQL from GitHub executed successfully!")

    except Exception as e:
        print("Error running GitHub SQL:", e)
    finally:
        if cur: cur.close()
        if conn: conn.close()

# Initialize DB and load test.sql
init_db()
run_github_sql()

# -------------------------
# Authentication Routes
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
            # Static admin login
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
            cur.execute("INSERT INTO users (Email, Username, Password) VALUES (%s, %s, %s)", (email, username, password))
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except psycopg.errors.UniqueViolation:
            flash("Username already taken.", "danger")
        except Exception as e:
            flash(f"DB Error: {e}", "danger")
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
# Dashboard Route
# -------------------------
def list_shots():
    shots_folder = os.path.join(app.static_folder, "shots")
    try:
        files = [f for f in os.listdir(shots_folder) if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif"))]
    except Exception:
        files = []
    return files

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
# Display Chicks Data
# -------------------------
@app.route("/chicks")
def chicks():
    if "user_role" not in session:
        return redirect(url_for("login"))

    data = []
    conn = cur = None
    try:
        conn = get_db_connection()
        cur = get_db_cursor(conn)
        cur.execute("SELECT * FROM chick_records ORDER BY registration_date DESC")
        data = [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print("Error fetching chicks:", e)
    finally:
        if cur: cur.close()
        if conn: conn.close()

    return render_template("chicks.html", chicks=data)

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
