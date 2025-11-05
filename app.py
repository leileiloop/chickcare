from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
import os
from functools import wraps
import logging

# DB libs
import psycopg  # core psycopg3
from psycopg.rows import dict_row
import psycopg.errors as pg_errors

# Password helpers
from werkzeug.security import generate_password_hash, check_password_hash

# Try to import the pool helper from the recommended package; fall back gracefully if not present.
try:
    # recommended separate package that provides a connection pool for psycopg3
    from psycopg_pool import ConnectionPool
    POOL_AVAILABLE = True
except Exception:
    ConnectionPool = None
    POOL_AVAILABLE = False

# -------------------------
# Flask app setup
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")

# Basic logger
logging.basicConfig(level=logging.INFO)

# --- REQUIRED ENV VARS (fail fast with helpful message) ---
required_env = ["SECRET_KEY", "DATABASE_URL", "SMTP_PASSWORD", "MAIL_USERNAME"]
missing = [v for v in required_env if v not in os.environ]
if missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

app.secret_key = os.environ["SECRET_KEY"]
DB_URL_RAW = os.environ["DATABASE_URL"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]
MAIL_USERNAME = os.environ["MAIL_USERNAME"]

# Normalize DB URL: ensure it has 'postgresql://' prefix (some platforms provide 'postgres://')
if DB_URL_RAW.startswith("postgres://"):
    DB_URL = DB_URL_RAW.replace("postgres://", "postgresql://", 1)
elif not DB_URL_RAW.startswith("postgresql://"):
    DB_URL = f"postgresql://{DB_URL_RAW}"
else:
    DB_URL = DB_URL_RAW

# Optional: production session cookie hardening
app.config.setdefault("SESSION_COOKIE_SECURE", os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true")
app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")

# -------------------------
# Database setup (Connection Pooling with fallback)
# -------------------------
pool = None
if POOL_AVAILABLE and ConnectionPool is not None:
    try:
        pool = ConnectionPool(conninfo=DB_URL, min_size=1, max_size=10)
        app.logger.info("Database connection pool created successfully (psycopg_pool).")
    except Exception as e:
        app.logger.error(f"Failed to create ConnectionPool: {e}")
        pool = None

if pool is None:
    app.logger.warning(
        "psycopg_pool not available or pool creation failed — "
        "falling back to connect-on-demand (no pooling). Install psycopg[binary,pool] (or psycopg_pool) for connection pooling."
    )

def get_conn():
    """
    Return a new psycopg connection (caller should close or use context manager).
    Connections use dict_row row factory so returned rows are dictionaries.
    Usage:
        with get_conn() as conn:
            with conn.cursor() as cur:
                ...
    """
    return psycopg.connect(DB_URL, row_factory=dict_row)

def get_conn_from_pool():
    """
    Return a connection from pool. Use as a context manager:
        with get_conn_from_pool() as conn:
            ...
    """
    return pool.connection()

def use_conn():
    """
    Helper to choose pooled connection if available else direct connect.
    Returns a context manager that yields a connection object with row_factory dict_row.
    """
    if pool:
        return get_conn_from_pool()
    else:
        return get_conn()

# -------------------------
# Flask-Mail setup
# -------------------------
app.config.update(
    MAIL_SERVER=os.environ.get("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_PORT=int(os.environ.get("MAIL_PORT", 587)),
    MAIL_USE_TLS=os.environ.get("MAIL_USE_TLS", "true").lower() == "true",
    MAIL_USERNAME=MAIL_USERNAME,
    MAIL_PASSWORD=SMTP_PASSWORD,
)
mail = Mail(app)
serializer = URLSafeTimedSerializer(app.secret_key)

# -------------------------
# Helper: Decorators
# -------------------------
def login_required(f):
    """Ensures a user is logged in."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    """Ensures a user is logged in AND has the 'admin' role."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if session.get("user_role") != "admin":
            flash("You do not have permission to access this page.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated

# -------------------------
# Helper: Current user fetch
# -------------------------
def get_current_user(user_id):
    """Return user dict from users table or None."""
    try:
        with use_conn() as conn:
            # ensure row factory
            conn.row_factory = dict_row
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, email, role, active FROM users WHERE id = %s", (user_id,))
                return cur.fetchone()
    except Exception as e:
        app.logger.exception("Failed to fetch current user")
        return None

# -------------------------
# ROUTES
# -------------------------
@app.route("/")
def home():
    return redirect(url_for("login"))

# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = None
        try:
            with use_conn() as conn:
                conn.row_factory = dict_row
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                    user = cur.fetchone()
        except Exception as e:
            app.logger.exception("Database error during login")
            flash("Database error. Please try again later.", "danger")
            return redirect(url_for("login"))

        if user and user.get("password"):
            if check_password_hash(user["password"], password):
                session["user_id"] = user["id"]
                session["user_role"] = user.get("role", "user")
                # store name/email for templates convenience
                session["user_name"] = user.get("name")
                session["user_email"] = user.get("email")
                flash(f"Welcome, {user.get('name', 'User')}!", "success")
                if session["user_role"] == "admin":
                    return redirect(url_for("admin_dashboard"))
                return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")

# REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        raw_password = request.form.get("password", "")
        password = generate_password_hash(raw_password)
        role = "user"

        try:
            with use_conn() as conn:
                conn.row_factory = dict_row
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                        (name, email, password, role),
                    )
                    conn.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except pg_errors.UniqueViolation:
            app.logger.info("Registration attempt for existing email: %s", email)
            flash("This email is already registered.", "danger")
        except Exception as e:
            app.logger.exception("Database error during registration")
            flash("Database error. Please try again later.", "danger")

    return render_template("register.html")

# DASHBOARD (for regular users)
@app.route("/dashboard")
@login_required
def dashboard():
    # example: pass some records or metrics (keep simple for now)
    # you can expand fetching real metrics here
    return render_template("dashboard.html")

# ADMIN DASHBOARD (for admins)
@app.route("/admin-dashboard")
@admin_required
def admin_dashboard():
    return render_template("admin-dashboard.html")

@app.route("/main-dashboard")
@login_required
def main_dashboard():
    return render_template("main-dashboard.html")

@app.route("/environment")
@login_required
def environment():
    # fetch environment data to show in template if desired
    environment_data = []
    try:
        with use_conn() as conn:
            conn.row_factory = dict_row
            with conn.cursor() as cur:
                cur.execute("SELECT temperature, humidity, date, time FROM environment ORDER BY date DESC, time DESC LIMIT 50")
                environment_data = cur.fetchall()
    except Exception:
        app.logger.exception("Failed to load environment data")
    return render_template("environment.html", environment_data=environment_data)

@app.route("/feed")
@login_required
def feed():
    feed_data = []
    try:
        with use_conn() as conn:
            conn.row_factory = dict_row
            with conn.cursor() as cur:
                cur.execute("SELECT date, feed_type, amount, time FROM feed ORDER BY date DESC LIMIT 50")
                feed_data = cur.fetchall()
    except Exception:
        app.logger.exception("Failed to load feed data")
    return render_template("feed.html", feed_data=feed_data)

@app.route("/growth")
@login_required
def growth():
    # fetch growth records for chart or table
    dates = []
    weights = []
    growth_data = []
    try:
        with use_conn() as conn:
            conn.row_factory = dict_row
            with conn.cursor() as cur:
                cur.execute("SELECT date, weight, height, feed_type FROM growth ORDER BY date ASC")
                rows = cur.fetchall()
                growth_data = rows
                dates = [r["date"].strftime("%Y-%m-%d") if hasattr(r["date"], "strftime") else r["date"] for r in rows]
                weights = [r["weight"] for r in rows]
    except Exception:
        app.logger.exception("Failed to load growth data")
    return render_template("growth.html", dates=dates, weights=weights, growth_data=growth_data)

@app.route("/data-table")
@login_required
def data_table():
    # return a table view for collected records (for your data_table.html)
    growth_data = []
    try:
        with use_conn() as conn:
            conn.row_factory = dict_row
            with conn.cursor() as cur:
                cur.execute("SELECT id, date, temperature, humidity, notes FROM sensor_data ORDER BY date DESC LIMIT 200")
                growth_data = cur.fetchall()
    except Exception:
        app.logger.exception("Failed to load data table")
    return render_template("data_table.html", growth_data=growth_data)

@app.route("/profile")
@login_required
def profile():
    user = None
    user_id = session.get("user_id")
    if user_id:
        user = get_current_user(user_id)
    return render_template("profile.html", user=user)

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        new_password = request.form.get("password", "")

        try:
            with use_conn() as conn:
                conn.row_factory = dict_row
                with conn.cursor() as cur:
                    if new_password:
                        hashed = generate_password_hash(new_password)
                        cur.execute("UPDATE users SET name=%s, email=%s, password=%s WHERE id=%s", (name, email, hashed, user_id))
                    else:
                        cur.execute("UPDATE users SET name=%s, email=%s WHERE id=%s", (name, email, user_id))
                    conn.commit()

            # update session values for templates
            session["user_name"] = name
            session["user_email"] = email
            flash("Settings updated successfully.", "success")
            return redirect(url_for("settings"))
        except Exception:
            app.logger.exception("Failed to update settings")
            flash("Failed to update settings. Please try again later.", "danger")
            return redirect(url_for("settings"))

    # GET: render current settings
    user = get_current_user(user_id)
    return render_template("settings.html", user=user)

@app.route("/manage-users")
@admin_required
def manage_users():
    users = []
    try:
        with use_conn() as conn:
            conn.row_factory = dict_row
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, email, role, active FROM users ORDER BY id DESC")
                users = cur.fetchall()
    except Exception:
        app.logger.exception("Failed to load users")
    return render_template("manage-users.html", users=users)

@app.route("/report")
@login_required
def report():
    # placeholder: you can populate with actual aggregated report data
    return render_template("report.html")

@app.route("/sanitization")
@login_required
def sanitization():
    sanitization_data = []
    try:
        with use_conn() as conn:
            conn.row_factory = dict_row
            with conn.cursor() as cur:
                cur.execute("SELECT date, time, area, method, remarks FROM sanitization ORDER BY date DESC LIMIT 50")
                sanitization_data = cur.fetchall()
    except Exception:
        app.logger.exception("Failed to load sanitization data")
    return render_template("sanitization.html", sanitization_data=sanitization_data)

# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    flash("You’ve been logged out.", "info")
    return redirect(url_for("login"))

# FORGOT PASSWORD
@app.route("/forgot", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        user = None
        try:
            with use_conn() as conn:
                conn.row_factory = dict_row
                with conn.cursor() as cur:
                    cur.execute("SELECT id, email FROM users WHERE email = %s", (email,))
                    user = cur.fetchone()
        except Exception:
            app.logger.exception("Database error during forgot_password")
            flash("Database error. Please try again later.", "danger")
            return redirect(url_for("forgot_password"))

        # Always show the same message to avoid account enumeration
        if user:
            token = serializer.dumps(email, salt="reset-password")
            reset_link = url_for("reset_password", token=token, _external=True)
            msg = Message(
                "Password Reset - ChickCare",
                sender=MAIL_USERNAME,
                recipients=[email],
            )
            msg.html = render_template("reset_email.html", reset_link=reset_link)
            try:
                mail.send(msg)
                app.logger.info(f"Sent password reset email to {email}")
            except Exception:
                app.logger.exception("Mail send failed")
                flash("Mail server error. Please contact the administrator.", "danger")
                return redirect(url_for("forgot_password"))

        flash("If your email is registered, instructions have been sent.", "info")
        return redirect(url_for("login"))

    return render_template("forgot.html")

# RESET PASSWORD
@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = serializer.loads(token, salt="reset-password", max_age=3600)
    except SignatureExpired:
        flash("This reset link has expired.", "danger")
        return redirect(url_for("forgot_password"))
    except BadSignature:
        flash("Invalid reset link.", "danger")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        new_password_raw = request.form.get("password", "")
        new_password = generate_password_hash(new_password_raw)
        try:
            with use_conn() as conn:
                conn.row_factory = dict_row
                with conn.cursor() as cur:
                    cur.execute("UPDATE users SET password = %s WHERE email = %s", (new_password, email))
                    conn.commit()
            flash("Password reset successful! Please log in.", "success")
        except Exception:
            app.logger.exception("Database error during password reset")
            flash("Database error. Please try again later.", "danger")
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token)

# -------------------------
# RUN APP (only for local dev)
# -------------------------
if __name__ == "__main__":
    # In production on Render the webserver (gunicorn) runs the app; don't enable debug there.
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
