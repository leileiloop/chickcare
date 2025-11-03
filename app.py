# app.py
import os
import secrets
import functools
import logging
import psycopg
from psycopg.rows import dict_row
from psycopg.errors import UniqueViolation, OperationalError
from flask import Flask, render_template, request, session, flash, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.mime.text import MIMEText

# -------------------------
# Basic Logging
# -------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("chickencare")

# -------------------------
# Flask App Config
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")
app.config["SESSION_COOKIE_SECURE"] = False  # True if using HTTPS

# -------------------------
# PostgreSQL Database Config
# -------------------------
DATABASE_URL = (
    "postgresql://chickencaredb_tnrw_user:"
    "S5Bb7GdOT6zDwYZy8uJrI762A8aq7nG4@"
    "dpg-d447gopr0fns73fssg5g-a.oregon-postgres.render.com/"
    "chickencaredb_tnrw"
)

def get_db_connection():
    try:
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    except OperationalError as e:
        log.exception("Database connection failed")
        raise ConnectionError(f"Database connection failed: {e}")

# -------------------------
# Gmail SMTP Config (for forgot password)
# -------------------------
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_EMAIL = "chickenmonitor1208@gmail.com"
SMTP_PASSWORD = "leinadloki012"

def send_reset_email(to_email, token):
    """Send a reset password email with link to reset form"""
    reset_link = url_for("reset_password", token=token, _external=True)
    subject = "ChickenCare — Reset Your Password"

    html_content = f"""
    <html><body style="font-family:Arial,sans-serif;">
        <h2>Password Reset Request</h2>
        <p>Hi,</p>
        <p>You recently requested to reset your password for your ChickenCare account.</p>
        <p>Click the button below to reset it:</p>
        <p>
            <a href="{reset_link}" style="padding:10px 20px;background:#4CAF50;color:white;text-decoration:none;border-radius:6px;">
                Reset Password
            </a>
        </p>
        <p>If you didn’t request a password reset, you can safely ignore this email.</p>
        <br>
        <p>— The ChickenCare Team</p>
    </body></html>
    """

    msg = MIMEText(html_content, "html")
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        log.info(f"Reset email successfully sent to {to_email}")
        return True
    except Exception as e:
        log.error(f"Error sending reset email: {e}")
        return False

# -------------------------
# Ensure Schema & Default Admin
# -------------------------
def ensure_schema():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    ALTER TABLE users
                    ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'user',
                    ADD COLUMN IF NOT EXISTS reset_token TEXT
                """)
                cur.execute("SELECT id FROM users WHERE Username=%s", ("admin",))
                if not cur.fetchone():
                    hashed_admin = generate_password_hash("admin")
                    cur.execute(
                        "INSERT INTO users (Email, Username, Password, role) VALUES (%s, %s, %s, %s)",
                        ("admin@chickencare.local", "admin", hashed_admin, "admin")
                    )
                    log.info("Default super admin created: username=admin, password=admin")
            conn.commit()
    except Exception:
        log.exception("Schema check failed")

ensure_schema()

# -------------------------
# Login Decorator
# -------------------------
def login_required(role=None):
    def decorator(view):
        @functools.wraps(view)
        def wrapped_view(*args, **kwargs):
            if "user_role" not in session:
                flash("Please login first.", "warning")
                return redirect(url_for("login"))
            if role and session.get("user_role") != role:
                flash("Access denied.", "danger")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped_view
    return decorator

# -------------------------
# Routes
# -------------------------
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()
        if not username or not password:
            error = "Enter both username and password."
        else:
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT * FROM users WHERE Username=%s", (username,))
                        user = cur.fetchone()
                        if user and check_password_hash(user["Password"], password):
                            session.clear()
                            session["user_role"] = user.get("role", "user")
                            session["email"] = user["Email"]
                            flash("Login successful!", "success")
                            return redirect(url_for("admin_dashboard") if session["user_role"] == "admin" else url_for("dashboard"))
                        else:
                            error = "Invalid username or password."
            except Exception as e:
                log.exception("Login failed")
                error = "Server error during login."
    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if not email or not username or not password:
            flash("All fields required.", "warning")
            return redirect(url_for("register"))

        hashed = generate_password_hash(password)
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO users (Email, Username, Password, role) VALUES (%s, %s, %s, %s)",
                                (email, username, hashed, "user"))
                conn.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for("login"))
        except UniqueViolation:
            flash("Username or email already exists.", "danger")
        except Exception:
            log.exception("Registration error")
            flash("Server error during registration.", "danger")
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have logged out.", "info")
    return redirect(url_for("login"))

# -------------------------
# Forgot & Reset Password
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
                        token = secrets.token_urlsafe(20)
                        cur.execute("UPDATE users SET reset_token=%s WHERE Email=%s", (token, email))
                        conn.commit()
                        send_reset_email(email, token)
                        flash("Password reset email sent. Check your inbox.", "success")
                    else:
                        flash("If the account exists, reset instructions have been sent.", "info")
        except Exception:
            log.exception("Forgot password error")
            flash("Error processing request.", "danger")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")

@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if request.method == "POST":
        password = request.form.get("password", "").strip()
        if not password:
            flash("Enter your new password.", "warning")
            return redirect(url_for("reset_password", token=token))
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM users WHERE reset_token=%s", (token,))
                    user = cur.fetchone()
                    if user:
                        hashed = generate_password_hash(password)
                        cur.execute("UPDATE users SET Password=%s, reset_token=NULL WHERE reset_token=%s", (hashed, token))
                        conn.commit()
                        flash("Password updated successfully. Please log in.", "success")
                        return redirect(url_for("login"))
                    else:
                        flash("Invalid or expired reset link.", "danger")
                        return redirect(url_for("forgot_password"))
        except Exception:
            log.exception("Reset password error")
            flash("Server error during reset.", "danger")
            return redirect(url_for("forgot_password"))
    return render_template("reset_password.html", token=token)

# -------------------------
# Dashboards
# -------------------------
@app.route("/dashboard")
@login_required(role="user")
def dashboard():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sensordata ORDER BY DateTime DESC LIMIT 10")
                env_data = cur.fetchall()
                cur.execute("SELECT * FROM sensordata4 ORDER BY DateTime DESC LIMIT 10")
                water_food_data = cur.fetchall()
    except Exception:
        log.exception("Error loading dashboard")
        env_data, water_food_data = [], []
        flash("Error loading dashboard data.", "danger")
    return render_template("dashboard.html", env_data=env_data, water_food_data=water_food_data)

@app.route("/admin_dashboard")
@login_required(role="admin")
def admin_dashboard():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, Email, Username, role FROM users ORDER BY id")
                users = cur.fetchall()
                cur.execute("SELECT DateTime, Water_Level, Food_Level FROM sensordata4 ORDER BY DateTime DESC LIMIT 10")
                notifications = cur.fetchall()
    except Exception:
        log.exception("Error loading admin dashboard")
        users, notifications = [], []
    return render_template("admin_dashboard.html", users=users, notifications=notifications)

# -------------------------
# Run App
# -------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
