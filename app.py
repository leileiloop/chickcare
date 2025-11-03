import os
import secrets
import functools
import psycopg
from psycopg.rows import dict_row
from psycopg.errors import UniqueViolation, OperationalError
from flask import Flask, render_template, jsonify, request, session, flash, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

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
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is not set.")
    conn_str = DATABASE_URL
    if conn_str.startswith("postgres://"):
        conn_str = conn_str.replace("postgres://", "postgresql://", 1)
    if "sslmode" not in conn_str:
        conn_str += "&sslmode=require" if "?" in conn_str else "?sslmode=require"
    return psycopg.connect(conn_str, row_factory=dict_row)

# -------------------------
# Utility Decorators
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
# Auth Routes
# -------------------------
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    # Redirect already logged-in users
    if "user_role" in session:
        role = session.get("user_role")
        if role == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("dashboard"))

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
            return redirect(url_for("admin_dashboard"))

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
            flash(f"Login failed: {e}", "danger")
            print(f"LOGIN ERROR: {e}")

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
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except UniqueViolation:
            flash("Username or email already exists.", "danger")
        except Exception as e:
            flash(f"Registration error: {e}", "danger")
            print(f"REGISTER ERROR: {e}")

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
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
                        flash(f"Temporary password: {temp_pass}", "success")  # Replace with real email in production
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
    if session.get("user_role") == "admin":
        return redirect(url_for("admin_dashboard"))
    return render_template("dashboard.html")

@app.route("/admin_dashboard")
@login_required
def admin_dashboard():
    if session.get("user_role") != "admin":
        flash("Admin only.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("admin-dashboard.html")
