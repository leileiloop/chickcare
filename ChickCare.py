from flask import Flask, render_template, jsonify, request, session, flash, url_for, redirect
import os
import psycopg2
import psycopg2.extras

# -------------------------
# App config
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = "supersecretkey"  # change in production

# -------------------------
# PostgreSQL DB config
# -------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")  # Set this in Render environment variables

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn

def get_db_cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# -------------------------
# Initialize DB (tables)
# -------------------------
def init_db():
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

    # Environment sensor table (sensordata)
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

    # Supplies (sensordata1)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sensordata1 (
        id SERIAL PRIMARY KEY,
        DateTime TIMESTAMP DEFAULT NOW(),
        Food TEXT,
        Water TEXT
    )
    """)

    # Sanitization (sensordata2)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sensordata2 (
        id SERIAL PRIMARY KEY,
        DateTime TIMESTAMP DEFAULT NOW(),
        Conveyor TEXT,
        Sprinkle TEXT,
        UVLight TEXT
    )
    """)

    # Growth / weights (sensordata3)
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

    # Water/Food levels (sensordata4)
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

    # Chick records (registration)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS chick_records (
        id SERIAL PRIMARY KEY,
        ChickNumber TEXT UNIQUE,
        registration_date TIMESTAMP DEFAULT NOW()
    )
    """)

    cur.close()
    conn.close()

# Initialize database at startup
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
            # Admin static login
            if username.lower() == "admin" and password == "admin":
                session["user_role"] = "admin"
                session["email"] = "admin@yourdomain.com"
                return redirect(url_for("dashboard"))

            conn = get_db_connection()
            cur = get_db_cursor(conn)
            cur.execute("SELECT * FROM users WHERE Username = %s AND Password = %s", (username, password))
            user = cur.fetchone()
            cur.close()
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
        cur = get_db_cursor(conn)
        try:
            cur.execute(
                "INSERT INTO users (Email, Username, Password) VALUES (%s, %s, %s)",
                (email, username, password)
            )
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except psycopg2.errors.UniqueViolation:
            flash("Username already taken.", "danger")
        finally:
            cur.close()
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
    conn = get_db_connection()
    cur = get_db_cursor(conn)
    cur.execute("SELECT DateTime, message FROM notifications ORDER BY DateTime DESC LIMIT 10")
    notifications = [dict(row) for row in cur.fetchall()]
    cur.execute("SELECT * FROM sensordata ORDER BY DateTime DESC LIMIT 1")
    latest_sensor = cur.fetchone()
    cur.close()
    conn.close()
    return render_template("dashboard.html", image_files=list_shots(), notifications=notifications, data=(dict(latest_sensor) if latest_sensor else None))

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
# API endpoints
# -------------------------
@app.route("/get_image_list")
def get_image_list():
    return jsonify(list_shots())

@app.route("/get_data")
def get_data():
    conn = get_db_connection()
    cur = get_db_cursor(conn)
    cur.execute("SELECT Temperature AS Temp, Humidity AS Hum, Light1, Light2, Ammonia AS Amm, ExhaustFan FROM sensordata ORDER BY DateTime DESC LIMIT 1")
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return jsonify(dict(row))
    return jsonify({"error": "No data found"}), 404

@app.route("/get_all_data")
def get_all_data():
    conn = get_db_connection()
    cur = get_db_cursor(conn)
    cur.execute("SELECT DateTime, Temperature, Humidity, Light1, Light2, Ammonia, ExhaustFan FROM sensordata ORDER BY DateTime DESC LIMIT 10")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(rows)

@app.route("/get_all_notifications")
def get_all_notifications():
    conn = get_db_connection()
    cur = get_db_cursor(conn)
    cur.execute("SELECT DateTime, message FROM notifications ORDER BY DateTime DESC LIMIT 50")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(rows)

@app.route("/insert_notifications", methods=["POST"])
def insert_notifications():
    payload = request.get_json() or {}
    items = payload.get("notifications") or payload.get("messages") or []
    if not items:
        return jsonify({"success": False, "message": "No notifications provided"}), 400
    conn = get_db_connection()
    cur = get_db_cursor(conn)
    for msg in items:
        cur.execute("INSERT INTO notifications (message) VALUES (%s)", (msg,))
    cur.close()
    conn.close()
    return jsonify({"success": True, "inserted": len(items)})

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
    cur = get_db_cursor(conn)
    cur.execute("UPDATE users SET Email=%s, Username=%s, Password=%s WHERE id=%s", (email, username, password, user_id))
    cur.close()
    conn.close()
    return jsonify({"success": True})

@app.route("/delete_user", methods=["POST"])
def delete_user():
    data = request.get_json() or {}
    user_id = data.get("id")
    if not user_id:
        return jsonify({"success": False, "message": "id required"}), 400
    conn = get_db_connection()
    cur = get_db_cursor(conn)
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
    cur.close()
    conn.close()
    return jsonify({"success": True})

@app.route("/get_filtered_data")
def get_filtered_data():
    record_type = request.args.get("recordType", "notifications")
    from_date = request.args.get("fromDate")
    to_date = request.args.get("toDate")
    search = request.args.get("search")
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
        where.append("DateTime BETWEEN %s AND %s")
        params.extend([from_date + " 00:00:00", to_date + " 23:59:59"])
    if search:
        where.append("message LIKE %s")
        params.append(f"%{search}%")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY DateTime DESC LIMIT 700"
    conn = get_db_connection()
    cur = get_db_cursor(conn)
    try:
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        cur.close()
        conn.close()
        return jsonify({"error": str(e)}), 500
    cur.close()
    conn.close()
    return jsonify(rows)

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
    app.run(host="0.0.0.0", port=8080, debug=True)
