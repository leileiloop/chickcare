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
# Database (use provided/default)
# -------------------------
# Either take from environment or fall back to the provided Render URL
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://chickencaredb_tnrw_user:S5Bb7GdOT6zDwYZy8uJrI762A8aq7nG4@dpg-d447gopr0fns73fssg5g-a.oregon-postgres.render.com/chickencaredb_tnrw"
)

def get_db_connection():
    """Return a new psycopg connection using dict-like rows."""
    try:
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    except OperationalError as e:
        log.exception("Database connection failed")
        raise ConnectionError(f"Database connection failed: {e}")

def normalize_row(row):
    """Convert row keys to lowercase for consistent access (Password vs password)."""
    if row is None:
        return None
    # dict_row already behaves like a dict; convert keys to lowercase
    return {k.lower(): v for k, v in dict(row).items()}

# -------------------------
# SMTP config (forgot password)
# -------------------------
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_EMAIL = os.environ.get("SMTP_EMAIL", "chickenmonitor1208@gmail.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "leinadloki012")  # recommended: move to env var

def send_reset_email(to_email: str, token: str) -> bool:
    """Send an HTML password reset email. Returns True on success."""
    try:
        reset_link = url_for("reset_password", token=token, _external=True)
    except RuntimeError:
        # no request context (unlikely here) -> fallback to localhost
        reset_link = f"http://127.0.0.1:8080/reset_password/{token}"

    subject = "ChickenCare — Reset your password"
    html_content = f"""
    <html><body style="font-family:Arial, sans-serif;">
      <h3>Password reset request</h3>
      <p>Click the button below to reset your ChickenCare password:</p>
      <p>
        <a href="{reset_link}" style="
            padding:10px 18px;
            background:#1f8ceb;
            color:#fff;
            text-decoration:none;
            border-radius:6px;
            display:inline-block;">
          Reset password
        </a>
      </p>
      <p>If you didn't request this, you can ignore this message.</p>
      <p>— ChickenCare</p>
    </body></html>
    """
    msg = MIMEText(html_content, "html")
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
    except Exception:
        log.exception("Failed to send reset email to %s", to_email)
        return False

# -------------------------
# Initialize DB schema & ensure super-admin
# -------------------------
def ensure_schema_and_admin():
    """
    Ensure optional columns exist and that a super-admin (username=admin) exists.
    This runs at app startup.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # add optional columns if missing
                cur.execute("""
                    ALTER TABLE users
                    ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'user',
                    ADD COLUMN IF NOT EXISTS reset_token TEXT
                """)
                # optionally create a notifications table if you wish to use it
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS notifications (
                        id SERIAL PRIMARY KEY,
                        DateTime TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                        message TEXT
                    )
                """)
                # ensure admin user exists
                cur.execute("SELECT id FROM users WHERE Username=%s", ("admin",))
                if not cur.fetchone():
                    hashed_admin = generate_password_hash("admin")
                    cur.execute(
                        "INSERT INTO users (Email, Username, Password, role) VALUES (%s, %s, %s, %s)",
                        ("admin@chickencare.local", "admin", hashed_admin, "admin")
                    )
                    log.info("Default admin created (username=admin, password=admin)")
            conn.commit()
    except Exception:
        log.exception("Schema / admin initialization failed (continuing)")

# run init at startup
ensure_schema_and_admin()

# -------------------------
# login_required decorator with optional role
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
                # redirect to appropriate dashboard so user isn't trapped at login page
                return redirect(url_for("dashboard") if session.get("user_role") == "user" else url_for("admin_dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator

# -------------------------
# Routes: login, register, logout
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
                            if session["user_role"] == "admin":
                                return redirect(url_for("admin_dashboard"))
                            else:
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
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not email or not username or not password:
            flash("All fields are required.", "warning")
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password)
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO users (Email, Username, Password, role) VALUES (%s, %s, %s, %s)",
                        (email, username, hashed_pw, "user")
                    )
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
    flash("You have logged out.", "info")
    return redirect(url_for("login"))

# -------------------------
# Forgot / Reset password
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
                    user_exists = cur.fetchone() is not None
                    token = secrets.token_urlsafe(24)
                    if user_exists:
                        cur.execute("UPDATE users SET reset_token=%s WHERE Email=%s", (token, email))
                        conn.commit()
                        sent = send_reset_email(email, token)
                        if sent:
                            flash("Password reset email sent. Check your inbox.", "success")
                        else:
                            # don't reveal internal failure; show friendly message
                            log.warning("send_reset_email failed for %s", email)
                            flash("Password reset email sent (if the account exists). Check inbox.", "info")
                    else:
                        # Always show the same friendly message so you don't leak account existence
                        flash("If the account exists, password reset instructions have been sent.", "info")
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

    # GET -> render reset form (template should include a hidden token or use URL)
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
                # normalize notification rows (lowercase keys) before passing to template
                notifications = [{k.lower(): v for k, v in dict(r).items()} for r in raw]
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
                notifications = [{k.lower(): v for k, v in dict(r).items()} for r in raw_notifs]
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
# Run (local)
# -------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)
