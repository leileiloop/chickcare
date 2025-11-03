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
# Logging
# -------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("chickencare")

# -------------------------
# Flask app
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")
app.config["SESSION_COOKIE_SECURE"] = False  # set True on HTTPS in production

# -------------------------
# Database
# -------------------------
# Use your Render external DB URL
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://chickencaredb_tnrw_user:S5Bb7GdOT6zDwYZy8uJrI762A8aq7nG4@dpg-d447gopr0fns73fssg5g-a.oregon-postgres.render.com/chickencaredb_tnrw"
)

def get_db_connection():
    """Connect to PostgreSQL using psycopg 3."""
    try:
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        return conn
    except Exception as e:
        log.exception("Database connection failed")
        raise ConnectionError(f"Database connection failed: {e}")

def normalize_row(row):
    return {k.lower(): v for k, v in dict(row).items()} if row else None

# -------------------------
# Email config (reset password)
# -------------------------
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_EMAIL = "chickenmonitor1208@gmail.com"
SMTP_PASSWORD = "leinadloki012"  # Consider moving this to Render environment variable

def send_reset_email(to_email: str, token: str) -> bool:
    """Send password reset link via Gmail."""
    reset_link = url_for("reset_password", token=token, _external=True)
    subject = "ChickenCare — Reset your password"
    html_content = f"""
    <html><body>
      <h2>Password Reset Request</h2>
      <p>Click the button below to reset your ChickenCare password:</p>
      <p>
        <a href="{reset_link}" style="background:#1f8ceb;color:white;padding:10px 16px;border-radius:5px;text-decoration:none;">Reset Password</a>
      </p>
      <p>If you didn't request this, ignore this message.</p>
    </body></html>
    """
    msg = MIMEText(html_content, "html")
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, [to_email], msg.as_string())
        log.info("Reset email sent to %s", to_email)
        return True
    except Exception:
        log.exception("Failed to send reset email to %s", to_email)
        return False

# -------------------------
# Ensure schema and admin
# -------------------------
def ensure_schema_and_admin():
    """Ensure user table has columns and super admin account."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    ALTER TABLE users
                    ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'user',
                    ADD COLUMN IF NOT EXISTS reset_token TEXT
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS notifications (
                        id SERIAL PRIMARY KEY,
                        DateTime TIMESTAMP DEFAULT NOW(),
                        message TEXT
                    )
                """)
                cur.execute("SELECT id FROM users WHERE username=%s", ("admin",))
                if not cur.fetchone():
                    hashed_admin = generate_password_hash("admin")
                    cur.execute("""
                        INSERT INTO users (email, username, password, role)
                        VALUES (%s, %s, %s, %s)
                    """, ("admin@chickencare.local", "admin", hashed_admin, "admin"))
                    log.info("Created default admin account (admin/admin)")
            conn.commit()
    except Exception:
        log.exception("Failed to ensure schema/admin")

ensure_schema_and_admin()

# -------------------------
# Auth helpers
# -------------------------
def login_required(role=None):
    def decorator(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            if "user_role" not in session:
                flash("Please log in first.", "warning")
                return redirect(url_for("login"))
            if role and session["user_role"] != role:
                flash("Access denied.", "danger")
                return redirect(url_for("dashboard") if session["user_role"] == "user" else url_for("admin_dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator

# -------------------------
# Routes
# -------------------------
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if not username or not password:
            error = "Please enter both username and password."
        else:
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
                        user = normalize_row(cur.fetchone())
                        if user and check_password_hash(user["password"], password):
                            session.clear()
                            session["user_role"] = user["role"]
                            session["email"] = user["email"]
                            session["username"] = user["username"]
                            flash(f"Welcome, {user['username']}!", "success")
                            if user["role"] == "admin":
                                return redirect(url_for("admin_dashboard"))
                            return redirect(url_for("dashboard"))
                        else:
                            error = "Invalid username or password."
            except Exception:
                log.exception("Login error")
                error = "Login failed: server error."
    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip()
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        if not email or not username or not password:
            flash("All fields required.", "warning")
            return redirect(url_for("register"))
        hashed = generate_password_hash(password)
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO users (email, username, password, role)
                        VALUES (%s, %s, %s, %s)
                    """, (email, username, hashed, "user"))
                conn.commit()
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("login"))
        except UniqueViolation:
            flash("Email or username already exists.", "danger")
        except Exception:
            log.exception("Registration failed")
            flash("Registration failed: server error.", "danger")
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have logged out.", "info")
    return redirect(url_for("login"))

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"].strip()
        if not email:
            flash("Enter your email.", "warning")
            return redirect(url_for("forgot_password"))
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM users WHERE email=%s", (email,))
                    user = cur.fetchone()
                    token = secrets.token_urlsafe(24)
                    if user:
                        cur.execute("UPDATE users SET reset_token=%s WHERE email=%s", (token, email))
                        conn.commit()
                        send_reset_email(email, token)
                    # Always show same message to prevent info leaks
                    flash("If registered, password reset instructions sent.", "info")
        except Exception:
            log.exception("Error in forgot_password")
            flash("Failed to process request: server error.", "danger")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")

@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if request.method == "POST":
        new_pw = request.form["password"].strip()
        if not new_pw:
            flash("Enter new password.", "warning")
            return redirect(url_for("reset_password", token=token))
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM users WHERE reset_token=%s", (token,))
                    if cur.fetchone():
                        hashed = generate_password_hash(new_pw)
                        cur.execute("UPDATE users SET password=%s, reset_token=NULL WHERE reset_token=%s", (hashed, token))
                        conn.commit()
                        flash("Password updated successfully.", "success")
                        return redirect(url_for("login"))
                    else:
                        flash("Invalid or expired link.", "danger")
                        return redirect(url_for("forgot_password"))
        except Exception:
            log.exception("Error in reset_password")
            flash("Failed to reset password: server error.", "danger")
            return redirect(url_for("forgot_password"))
    return render_template("reset_password.html", token=token)

@app.route("/dashboard")
@login_required("user")
def dashboard():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT datetime, message FROM notifications ORDER BY datetime DESC LIMIT 10")
                notifications = [normalize_row(r) for r in cur.fetchall()]
    except Exception:
        log.exception("Dashboard error")
        notifications = []
    return render_template("dashboard.html", notifications=notifications)

@app.route("/admin_dashboard")
@login_required("admin")
def admin_dashboard():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, email, username, role FROM users ORDER BY id")
                users = [normalize_row(u) for u in cur.fetchall()]
                cur.execute("SELECT datetime, message FROM notifications ORDER BY datetime DESC LIMIT 10")
                notifications = [normalize_row(n) for n in cur.fetchall()]
    except Exception:
        log.exception("Admin dashboard error")
        users, notifications = [], []
    return render_template("admin_dashboard.html", users=users, notifications=notifications)

@app.route("/health")
def health():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return {"status": "ok"}, 200
    except Exception:
        return {"status": "error"}, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)
