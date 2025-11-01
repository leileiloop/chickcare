from flask import Flask, render_template, jsonify, request, session, flash, url_for, redirect
import os
import psycopg  # psycopg3, compatible with Python 3.13

# -------------------------
# App Configuration
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")  # override in Render

# -------------------------
# Database Configuration
# -------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set.")

def get_db_connection():
    # For external Postgres hosts (Render, Heroku), use sslmode=require
    return psycopg.connect(DATABASE_URL + "?sslmode=require", autocommit=True)

def get_db_cursor(conn):
    return conn.cursor(row_factory=psycopg.rows.dict_row)

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
                cur.execute(
                    "SELECT * FROM users WHERE Username=%s AND Password=%s",
                    (username, password)
                )
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
            cur.execute(
                "INSERT INTO users (Email, Username, Password) VALUES (%s, %s, %s)",
                (email, username, password)
            )
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
# Chicks Data Route
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
