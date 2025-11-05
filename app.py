from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
import logging
import psycopg
from psycopg.rows import dict_row
import psycopg.errors as pg_errors

# -------------------------
# Flask app setup
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
logging.basicConfig(level=logging.INFO)

# -------------------------
# Environment variables
# -------------------------
required_env = ["SECRET_KEY", "DATABASE_URL", "MAIL_USERNAME", "SMTP_PASSWORD"]
missing = [v for v in required_env if v not in os.environ]
if missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

app.secret_key = os.environ["SECRET_KEY"]
DB_URL_RAW = os.environ["DATABASE_URL"]
MAIL_USERNAME = os.environ["MAIL_USERNAME"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]

# Normalize DB URL for psycopg
DB_URL = DB_URL_RAW.replace("postgres://", "postgresql://", 1) \
    if DB_URL_RAW.startswith("postgres://") else DB_URL_RAW

# Session security
app.config.update(
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)

# -------------------------
# Database helper
# -------------------------
def get_conn():
    """Return a new PostgreSQL connection with dict_row factory."""
    return psycopg.connect(DB_URL, row_factory=dict_row)

def use_conn():
    """Context manager for database connection."""
    return get_conn()

# -------------------------
# Flask-Mail setup
# -------------------------
app.config.update(
    MAIL_SERVER="smtp.gmail.com",
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=MAIL_USERNAME,
    MAIL_PASSWORD=SMTP_PASSWORD
)
mail = Mail(app)
serializer = URLSafeTimedSerializer(app.secret_key)

# -------------------------
# Decorators
# -------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if session.get("user_role") != "admin":
            flash("You do not have permission to access this page.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return wrapper

# -------------------------
# Helper functions
# -------------------------
def get_current_user(user_id):
    try:
        with use_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, name, email, role, active FROM users WHERE id = %s", (user_id,))
            return cur.fetchone()
    except Exception:
        app.logger.exception("Failed to fetch current user")
        return None

def create_super_admin():
    """Automatically create super admin if not exists."""
    email = "admin"
    password = "admin"
    try:
        with use_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email=%s", (email,))
            if not cur.fetchone():
                hashed = generate_password_hash(password)
                cur.execute(
                    "INSERT INTO users (name,email,password,role,active) VALUES (%s,%s,%s,%s,%s)",
                    ("Super Admin", email, hashed, "admin", True)
                )
                conn.commit()
                app.logger.info("Super admin created")
            else:
                app.logger.info("Super admin already exists")
    except Exception:
        app.logger.exception("Failed to create super admin")

create_super_admin()

# -------------------------
# Routes
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
        try:
            with use_conn() as conn, conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                user = cur.fetchone()
        except Exception:
            app.logger.exception("DB error during login")
            flash("Database error. Try again later.", "danger")
            return redirect(url_for("login"))

        if user and check_password_hash(user["password"], password):
            session.update({
                "user_id": user["id"],
                "user_role": user.get("role", "user"),
                "user_name": user.get("name"),
                "user_email": user.get("email")
            })
            flash(f"Welcome, {user.get('name', 'User')}!", "success")
            return redirect(url_for("admin_dashboard") if user.get("role") == "admin" else url_for("dashboard"))

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
        try:
            with use_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (name,email,password,role) VALUES (%s,%s,%s,%s)",
                    (name, email, password, "user")
                )
                conn.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except pg_errors.UniqueViolation:
            flash("This email is already registered.", "danger")
        except Exception:
            app.logger.exception("Database error during registration")
            flash("Database error. Try again later.", "danger")
    return render_template("register.html")

# DASHBOARD
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

# ADMIN DASHBOARD
@app.route("/admin-dashboard")
@admin_required
def admin_dashboard():
    return render_template("admin-dashboard.html")

# ENVIRONMENT
@app.route("/environment")
@login_required
def environment():
    data = []
    try:
        with use_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT temperature, humidity, date, time FROM environment ORDER BY date DESC, time DESC LIMIT 50")
            data = cur.fetchall()
    except Exception:
        app.logger.exception("Failed to load environment data")
    return render_template("environment.html", environment_data=data)

# FEED
@app.route("/feed")
@login_required
def feed():
    data = []
    try:
        with use_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT date, feed_type, amount, time FROM feed ORDER BY date DESC LIMIT 50")
            data = cur.fetchall()
    except Exception:
        app.logger.exception("Failed to load feed data")
    return render_template("feed.html", feed_data=data)

# GROWTH
@app.route("/growth")
@login_required
def growth():
    dates, weights, growth_data = [], [], []
    try:
        with use_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT date, weight, height, feed_type FROM growth ORDER BY date ASC")
            rows = cur.fetchall()
            growth_data = rows
            dates = [r["date"].strftime("%Y-%m-%d") if hasattr(r["date"], "strftime") else r["date"] for r in rows]
            weights = [r["weight"] for r in rows]
    except Exception:
        app.logger.exception("Failed to load growth data")
    return render_template("growth.html", dates=dates, weights=weights, growth_data=growth_data)

# DATA TABLE
@app.route("/data-table")
@login_required
def data_table():
    data = []
    try:
        with use_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, date, temperature, humidity, notes FROM sensor_data ORDER BY date DESC LIMIT 200")
            data = cur.fetchall()
    except Exception:
        app.logger.exception("Failed to load data table")
    return render_template("data_table.html", growth_data=data)

# PROFILE
@app.route("/profile")
@login_required
def profile():
    user = get_current_user(session.get("user_id"))
    return render_template("profile.html", user=user)

# SETTINGS
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user_id = session.get("user_id")
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        new_password = request.form.get("password", "")
        try:
            with use_conn() as conn, conn.cursor() as cur:
                if new_password:
                    hashed = generate_password_hash(new_password)
                    cur.execute("UPDATE users SET name=%s,email=%s,password=%s WHERE id=%s", (name,email,hashed,user_id))
                else:
                    cur.execute("UPDATE users SET name=%s,email=%s WHERE id=%s", (name,email,user_id))
                conn.commit()
            session["user_name"] = name
            session["user_email"] = email
            flash("Settings updated successfully.", "success")
            return redirect(url_for("settings"))
        except Exception:
            app.logger.exception("Failed to update settings")
            flash("Failed to update settings. Try again later.", "danger")
    user = get_current_user(user_id)
    return render_template("settings.html", user=user)

# MANAGE USERS
@app.route("/manage-users")
@admin_required
def manage_users():
    users = []
    try:
        with use_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT id,name,email,role,active FROM users ORDER BY id DESC")
            users = cur.fetchall()
    except Exception:
        app.logger.exception("Failed to load users")
    return render_template("manage-users.html", users=users)

# SANITIZATION
@app.route("/sanitization")
@login_required
def sanitization():
    data = []
    try:
        with use_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT date,time,area,method,remarks FROM sanitization ORDER BY date DESC LIMIT 50")
            data = cur.fetchall()
    except Exception:
        app.logger.exception("Failed to load sanitization data")
    return render_template("sanitization.html", sanitization_data=data)

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
            with use_conn() as conn, conn.cursor() as cur:
                cur.execute("SELECT id,email FROM users WHERE email=%s", (email,))
                user = cur.fetchone()
        except Exception:
            app.logger.exception("Database error during forgot_password")
            flash("Database error. Try again later.", "danger")
            return redirect(url_for("forgot_password"))

        if user:
            token = serializer.dumps(email, salt="reset-password")
            reset_link = url_for("reset_password", token=token, _external=True)
            msg = Message("Password Reset - ChickCare", sender=MAIL_USERNAME, recipients=[email])
            msg.html = render_template("reset_email.html", reset_link=reset_link)
            try:
                mail.send(msg)
            except Exception:
                app.logger.exception("Mail send failed")
                flash("Mail server error. Contact admin.", "danger")
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
        new_password = generate_password_hash(request.form.get("password", ""))
        try:
            with use_conn() as conn, conn.cursor() as cur:
                cur.execute("UPDATE users SET password=%s WHERE email=%s", (new_password, email))
                conn.commit()
            flash("Password reset successful! Please log in.", "success")
        except Exception:
            app.logger.exception("Database error during password reset")
            flash("Database error. Try again later.", "danger")
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token)

# -------------------------
# Run app
# -------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
