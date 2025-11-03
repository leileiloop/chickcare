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
    """Connect to PostgreSQL safely."""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is not set.")

    conn_str = DATABASE_URL
    if conn_str.startswith("postgres://"):
        conn_str = conn_str.replace("postgres://", "postgresql://", 1)
    if "sslmode" not in conn_str:
        conn_str += "&sslmode=require" if "?" in conn_str else "?sslmode=require"

    try:
        return psycopg.connect(conn_str, row_factory=dict_row)
    except OperationalError as e:
        print(f"[DB CONNECTION ERROR] {e}")
        raise ConnectionError("Database connection failed.")

# -------------------------
# Decorators
# -------------------------
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if "user_role" not in session:
            flash("You must log in first.", "warning")
            return redirect(url_for("login"))
        return view(**kwargs)
    return wrapped_view

# -------------------------
# Utility Functions
# -------------------------
def list_shots():
    shots_dir = os.path.join(app.static_folder, "shots")
    return [f for f in os.listdir(shots_dir) if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif"))] if os.path.exists(shots_dir) else []

def fetch_latest_data(table_name, column_mappings=None):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                select_cols = "*"
                if column_mappings:
                    parts = []
                    for db_col, api_col in column_mappings.items():
                        if any(k in db_col.lower() for k in ['light','fan','control','food','water','conveyor','uv','sprinkle']):
                            parts.append(f"CASE WHEN UPPER({db_col}::text)='ON' THEN 'ON' ELSE 'OFF' END AS {api_col}")
                        else:
                            parts.append(f"{db_col} AS {api_col}")
                    select_cols = ", ".join(parts)
                cur.execute(f"SELECT {select_cols} FROM {table_name} ORDER BY DateTime DESC LIMIT 1")
                return cur.fetchone() or {}
    except Exception as e:
        print(f"[FETCH LATEST DATA ERROR] {e}")
        return {"error": str(e)}

def fetch_history_data(table_name, column_mappings=None, limit=50):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                select_cols = "*"
                if column_mappings:
                    parts = []
                    for db_col, api_col in column_mappings.items():
                        if any(k in db_col.lower() for k in ['conveyor','uv','sprinkle']):
                            parts.append(f"CASE WHEN UPPER({db_col}::text)='ON' THEN 'ON' ELSE 'OFF' END AS {api_col}")
                        else:
                            parts.append(f"{db_col} AS {api_col}")
                    select_cols = ", ".join(parts)
                cur.execute(f"SELECT {select_cols} FROM {table_name} ORDER BY DateTime DESC LIMIT {limit}")
                return cur.fetchall()
    except Exception as e:
        print(f"[FETCH HISTORY DATA ERROR] {e}")
        return []

# -------------------------
# Authentication Routes
# -------------------------
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Provide username and password.", "warning")
            return redirect(url_for("login"))

        # Admin login
        if username.lower() == "admin" and password == "admin":
            session.clear()
            session["user_role"] = "admin"
            session["email"] = "admin@domain.com"
            flash("Admin logged in.", "success")
            return redirect(url_for("dashboard"))

        # Regular user login
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
                        flash("Invalid credentials.", "danger")
        except Exception as e:
            print(f"[LOGIN ERROR] {e}")
            flash("Login failed due to server error.", "danger")

    return render_template("login.html")

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
            print(f"[REGISTER ERROR] {e}")
            flash("Registration failed due to server error.", "danger")

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))

# -------------------------
# Password Reset
# -------------------------
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
                        flash(f"Temporary password: {temp_pass}", "success")  # For testing only
                    else:
                        flash("If registered, password reset sent.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            print(f"[FORGOT PASSWORD ERROR] {e}")
            flash("Password reset failed.", "danger")
            return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")
