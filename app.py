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
app.config["SESSION_COOKIE_SECURE"] = False  # set True on HTTPS/production

# -------------------------
# DATABASE (Render / Provided)
# -------------------------
DATABASE_URL = os.environ.get("DATABASE_URL") or (
    "postgresql://chickencaredb_tnrw_user:"
    "S5Bb7GdOT6zDwYZy8uJrI762A8aq7nG4@"
    "dpg-d447gopr0fns73fssg5g-a.oregon-postgres.render.com/"
    "chickencaredb_tnrw"
)

def get_db_connection():
    """Return a new DB connection using psycopg with dict rows."""
    try:
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    except OperationalError as e:
        log.exception("DB connect failed")
        raise ConnectionError(f"Database connection failed: {e}")

def normalize_row(row):
    """
    Convert dict_row keys to lower-case keys for robust access:
    e.g. row['Password'] or row['password'] will be available as r['password'].
    """
    if row is None:
        return None
    return {k.lower(): v for k, v in dict(row).items()}

# -------------------------
# SMTP config (forgot password)
# -------------------------
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_EMAIL = os.environ.get("SMTP_EMAIL", "chickenmonitor1208@gmail.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "leinadloki012")  # use env var in production

def send_reset_email(to_email: str, token: str) -> bool:
    """
    Send a password reset email containing a link to /reset_password/<token>.
    _external True will create full URL based on request environment.
    """
    try:
        reset_link = url_for("reset_password", token=token, _external=True)
    except RuntimeError:
        # url_for with _external requires request context; fallback to localhost link
        reset_link = f"http://127.0.0.1:8080/reset_password/{token}"

    subject = "ChickenCare — Password reset"
    html = f"""
    <html><body style="font-family: Arial, sans-serif;">
      <p>Hello,</p>
      <p>You requested a password reset for your ChickenCare account. Click below to reset:</p>
      <p><a href="{reset_link}" style="padding:10px 20px;background:#1f8ceb;color:#fff;text-decoration:none;border-radius:6px;">Reset password</a></p>
      <p>If you didn't request this, ignore this email.</p>
      <p>— ChickenCare</p>
    </body></html>
    """

    msg = MIMEText(html, "html")
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, [to_email], msg.as_string())
        log.info("Reset email sent to %s", to_email)
        return True
    except Exception as e:
        log.exception("Failed to send reset email")
        return False

# -------------------------
# DB initialization: add columns & ensure admin
# -------------------------
def ensure_schema_and_admin():
    """Add optional columns if missing and ensure default super-admin exists."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # add role and reset_token columns if they don't exist
                cur.execute("""
                    ALTER TABLE users
                    ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'user',
                    ADD COLUMN IF NOT EXISTS reset_token TEXT
                """)
                # create notifications table if not exist (optional helper)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS notifications (
                        id SERIAL PRIMARY KEY,
                        DateTime TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                        message TEXT
                    )
                """)
                # ensure admin exists
                cur.execute("SELECT id FROM users WHERE Username=%s", ("admin",))
                if not cur.fetchone():
                    hashed = generate_password_hash("admin")
                    cur.execute(
                        "INSERT INTO users (Email, Username, Password, role) VALUES (%s,%s,%s,%s)",
                        ("admin@chickencare.local", "admin", hashed, "admin")
                    )
                    log.info("Default admin created (username=admin password=admin)")
            conn.commit()
    except Exception:
        log.exception("Failed to ensure schema/admin")

# run at import/start
ensure_schema_and_admin()

# -------------------------
# Login decorator
# -------------------------
def login_required(role=None):
    def decorator(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            if "user_role" not in session:
                flash("Please log in first.", "warning")
                return redirect(url_for("login"))
            if role and session.get("user_role") != role:
                flash("Access denied.", "danger")
                # send to appropriate dashboard instead of login to avoid loops
                return redirect(url_for("dashboard") if session.get("user_role") == "user" else url_for("admin_dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator

# -------------------------
# Routes: login/register/logout
# -------------------------
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if not username or not password:
            error = "Please enter username and password."
        else:
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT * FROM users WHERE Username=%s", (username,))
                        raw = cur.fetchone()
                        user = normalize_row(raw)
                        if user and user.get("password") and check_password_hash(user["password"], password):
                            # login success
                            session.clear()
                            session["user_role"] = user.get("role", "user")
                            session["email"] = user.get("email")
                            session["username"] = user.get("username")
                            flash(f"Welcome, {session['username']}!", "success")
                            return redirect(url_for("admin_dashboard") if session["user_role"] == "admin" else url_for("dashboard"))
                        else:
                            error = "Invalid credentials."
            except Exception:
                log.exception("Login error")
                error = "Login failed: server error."
    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if not email or not username or not password:
            flash("All fields are required.", "warning")
            return redirect(url_for("register"))

        hashed = generate_password_hash(password)
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO users (Email, Username, Password, role) VALUES (%s,%s,%s,%s)",
                                (email, username, hashed, "user"))
                conn.commit()
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("login"))
        except UniqueViolation:
            flash("Username or email already exists.", "danger")
        except Exception:
            log.exception("Registration error")
            flash("Registration failed: server error.", "danger")
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))

# -------------------------
# Password reset flow
# -------------------------
@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if not email:
            flash("Enter your email address.", "warning")
            return redirect(url_for("forgot_password"))
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM users WHERE Email=%s", (email,))
                    user = cur.fetchone()
                    token = secrets.token_urlsafe(24)
                    if user:
                        cur.execute("UPDATE users SET reset_token=%s WHERE Email=%s", (token, email))
                        conn.commit()
                        sent = send_reset_email(email, token)
                        if sent:
                            flash("Password reset email sent. Check your inbox.", "success")
                        else:
                            # still show friendly message to avoid exposing whether email exists
                            log.warning("Failed send_reset_email for %s", email)
                            flash("Password reset email sent (if account exists). Check inbox.", "info")
                    else:
                        # Friendly, non-confirming message
                        flash("If the account exists, password reset instructions were sent.", "info")
        except Exception:
            log.exception("Error in forgot_password")
            flash("Failed to process request: server error.", "danger")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")

@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if request.method == "POST":
        new_pw = request.form.get("password", "").strip()
        if not new_pw:
            flash("Enter a new password.", "warning")
            return redirect(url_for("reset_password", token=token))
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM users WHERE reset_token=%s", (token,))
                    user = cur.fetchone()
                    if user:
                        hashed = generate_password_hash(new_pw)
                        cur.execute("UPDATE users SET Password=%s, reset_token=NULL WHERE reset_token=%s", (hashed, token))
                        conn.commit()
                        flash("Password updated — please log in with your new password.", "success")
                        return redirect(url_for("login"))
                    else:
                        flash("Invalid or expired reset link.", "danger")
                        return redirect(url_for("forgot_password"))
        except Exception:
            log.exception("Error in reset_password")
            flash("Failed to reset password: server error.", "danger")
            return redirect(url_for("forgot_password"))
    # GET -> show reset form
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
                cur.execute("SELECT DateTime, message FROM notifications ORDER BY DateTime DESC LIMIT 10")
                raw = cur.fetchall()
                notifications = [normalize_row(r) for r in raw]
    except Exception:
        log.exception("Dashboard load error")
        notifications = []
        flash("Error loading dashboard data.", "danger")
    return render_template("dashboard.html", notifications=notifications)

@app.route("/admin_dashboard")
@login_required(role="admin")
def admin_dashboard():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, Email, Username, role FROM users ORDER BY id")
                raw_users = cur.fetchall()
                users = [normalize_row(u) for u in raw_users]
                cur.execute("SELECT DateTime, message FROM notifications ORDER BY DateTime DESC LIMIT 10")
                raw_notifs = cur.fetchall()
                notifications = [normalize_row(n) for n in raw_notifs]
    except Exception:
        log.exception("Admin dashboard error")
        users, notifications = [], []
        flash("Error loading admin data.", "danger")
    return render_template("admin_dashboard.html", users=users, notifications=notifications)

# -------------------------
# Health check
# -------------------------
@app.route("/health")
def health():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return {"status": "ok"}, 200
    except Exception:
        return {"status": "error"}, 500

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    # When running locally: debug True. For production set DEBUG/ENV via env vars.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)
