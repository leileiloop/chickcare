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
# Flask App Setup
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
logging.basicConfig(level=logging.INFO)

# -------------------------
# Environment Variables
# -------------------------
required_env = ["SECRET_KEY", "DATABASE_URL", "MAIL_USERNAME", "SMTP_PASSWORD"]
missing = [v for v in required_env if v not in os.environ]
if missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

app.secret_key = os.environ["SECRET_KEY"]
DB_URL_RAW = os.environ["DATABASE_URL"]
MAIL_USERNAME = os.environ["MAIL_USERNAME"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]

# Fix Postgres URL for psycopg
DB_URL = DB_URL_RAW.replace("postgres://", "postgresql://", 1) if DB_URL_RAW.startswith("postgres://") else DB_URL_RAW

# -------------------------
# Flask-Mail Setup
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
# Session Security
# -------------------------
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)

# -------------------------
# Database Helper
# -------------------------
def get_conn():
    return psycopg.connect(DB_URL, row_factory=dict_row)

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

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def wrapper(*args, **kwargs):
            if session.get("user_role") not in roles:
                flash("You do not have permission to access this page.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return wrapper
    return decorator

# -------------------------
# User Helpers
# -------------------------
def get_user_by_email(email):
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email=%s", (email,))
            return cur.fetchone()
    except Exception:
        app.logger.exception("Error fetching user by email")
        return None

def get_user_by_id(user_id):
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
            return cur.fetchone()
    except Exception:
        app.logger.exception("Error fetching user by ID")
        return None

def get_current_user():
    user_id = session.get("user_id")
    return get_user_by_id(user_id) if user_id else None

def create_superadmin():
    """Create default superadmin if none exists"""
    super_email = "superadmin@example.com"
    super_username = "admin"
    super_pass = generate_password_hash("admin")
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE role='superadmin'")
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO users (username,email,password,role) VALUES (%s,%s,%s,%s)",
                    (super_username, super_email, super_pass, "superadmin")
                )
                conn.commit()
                app.logger.info("Superadmin created")
            else:
                app.logger.info("Superadmin already exists")
    except Exception:
        app.logger.exception("Failed to create superadmin")

create_superadmin()

# -------------------------
# Routes
# -------------------------
@app.route("/")
def home():
    role = session.get("user_role")
    if role in ["admin", "superadmin"]:
        return redirect(url_for("admin_dashboard"))
    elif role:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

# ----- Auth -----
@app.route("/login", methods=["GET","POST"])
def login():
    if "user_id" in session:
        role = session.get("user_role")
        return redirect(url_for("admin_dashboard") if role in ["admin","superadmin"] else url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email","").strip()
        password = request.form.get("password","")
        user = get_user_by_email(email)
        if user and check_password_hash(user["password"], password):
            session.update({
                "user_id": user["id"],
                "user_role": user.get("role","user"),
                "user_username": user.get("username"),
                "user_email": user.get("email")
            })
            flash(f"Welcome, {user.get('username','User')}!", "success")
            return redirect(url_for("admin_dashboard") if user.get("role") in ["admin","superadmin"] else url_for("dashboard"))
        flash("Invalid email or password", "danger")
    return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if "user_id" in session:
        role = session.get("user_role")
        return redirect(url_for("admin_dashboard") if role in ["admin","superadmin"] else url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username","").strip()
        email = request.form.get("email","").strip()
        password = request.form.get("password","")
        if not username or not email or not password:
            flash("All fields are required.", "warning")
            return redirect(url_for("register"))
        hashed = generate_password_hash(password)
        try:
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (username,email,password,role) VALUES (%s,%s,%s,%s)",
                    (username,email,hashed,"user")
                )
                conn.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except pg_errors.UniqueViolation:
            flash("Email already registered.", "danger")
        except Exception:
            app.logger.exception("Registration failed")
            flash("Database error. Try again later.", "danger")
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))

# ----- Dashboard -----
@app.route("/dashboard")
@login_required
def dashboard():
    records = []
    total_chickens = 0
    temperature = 0
    humidity = 0
    upcoming_feeding = "N/A"

    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Fetch last 5 records
            cur.execute("SELECT * FROM sensordata ORDER BY id DESC LIMIT 5")
            records = cur.fetchall()

            # Total chickens
            cur.execute("SELECT COUNT(*) AS total FROM chickens")
            total_chickens = cur.fetchone()["total"]

            # Latest temperature and humidity
            if records:
                temperature = records[0]["temperature"]
                humidity = records[0]["humidity"]

            # Next feeding
            cur.execute("SELECT feed_time FROM feeding_schedule WHERE feed_time > NOW() ORDER BY feed_time ASC LIMIT 1")
            feed = cur.fetchone()
            if feed:
                upcoming_feeding = feed["feed_time"].strftime("%H:%M")
    except Exception:
        app.logger.exception("Failed to fetch dashboard data")
        flash("Could not load dashboard data.", "warning")

    return render_template(
        "dashboard.html",
        records=records,
        total_chickens=total_chickens,
        temperature=temperature,
        humidity=humidity,
        upcoming_feeding=upcoming_feeding
    )

@app.route("/admin-dashboard")
@role_required("admin","superadmin")
def admin_dashboard():
    return render_template("admin-dashboard.html")

# ----- Profile & Settings -----
@app.route("/profile")
@login_required
def profile():
    user = get_current_user()
    return render_template("profile.html", user=user)

@app.route("/settings", methods=["GET","POST"])
@login_required
def settings():
    user = get_current_user()
    if request.method == "POST":
        username = request.form.get("username","").strip()
        email = request.form.get("email","").strip()
        new_pass = request.form.get("password","")
        if not username or not email:
            flash("Username and email cannot be empty.", "warning")
            return redirect(url_for("settings"))
        try:
            with get_conn() as conn, conn.cursor() as cur:
                if new_pass:
                    cur.execute(
                        "UPDATE users SET username=%s,email=%s,password=%s WHERE id=%s",
                        (username,email,generate_password_hash(new_pass),user["id"])
                    )
                else:
                    cur.execute(
                        "UPDATE users SET username=%s,email=%s WHERE id=%s",
                        (username,email,user["id"])
                    )
                conn.commit()
            session.update({"user_username":username,"user_email":email})
            flash("Settings updated successfully.", "success")
            return redirect(url_for("settings"))
        except Exception:
            app.logger.exception("Failed to update settings")
            flash("Update failed. Try again later.", "danger")
    return render_template("settings.html", user=user)

# ----- Manage Users -----
@app.route("/manage-users")
@role_required("admin","superadmin")
def manage_users():
    users = []
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT id,username,email,role FROM users ORDER BY id DESC")
            users = cur.fetchall()
    except Exception:
        app.logger.exception("Failed to load users")
    return render_template("manage-users.html", users=users)

# ----- Password Reset -----
@app.route("/generate", methods=["GET","POST"])
def generate():
    if request.method == "POST":
        email = request.form.get("email","").strip()
        user = get_user_by_email(email)
        if user:
            try:
                token = serializer.dumps(email, salt="password-reset-salt")
                reset_url = url_for("reset_with_token", token=token, _external=True)
                msg = Message(
                    "ChickCare Password Reset",
                    sender=MAIL_USERNAME,
                    recipients=[email],
                    body=f"Hi {user['username']},\nClick the link below to reset your password:\n{reset_url}\nIf you didn't request this, ignore this email."
                )
                mail.send(msg)
                flash("Password reset link sent! Check your email.", "info")
            except Exception:
                app.logger.exception("Failed to send email")
                flash("Failed to send reset email. Try again later.", "danger")
        else:
            flash("Email not found.", "warning")
    return render_template("generate.html")

@app.route("/reset/<token>", methods=["GET","POST"])
def reset_with_token(token):
    try:
        email = serializer.loads(token, salt="password-reset-salt", max_age=3600)
    except SignatureExpired:
        flash("The link has expired.", "danger")
        return redirect(url_for("generate"))
    except BadSignature:
        flash("Invalid or tampered token.", "danger")
        return redirect(url_for("generate"))

    if request.method == "POST":
        password = request.form.get("password","")
        if not password:
            flash("Password cannot be empty.", "warning")
            return redirect(url_for("reset_with_token", token=token))
        try:
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET password=%s WHERE email=%s",
                    (generate_password_hash(password), email)
                )
                conn.commit()
            flash("Password reset successful! You can now log in.", "success")
            return redirect(url_for("login"))
        except Exception:
            app.logger.exception("Password reset failed")
            flash("Could not reset password. Try again later.", "danger")
    return render_template("reset_password.html", token=token)

# ----- Feature Pages -----
@app.route("/growth-monitoring")
@login_required
def growth_monitoring():
    return render_template("growth.html")

@app.route("/environment")
@login_required
def environment():
    data = []
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM sensordata ORDER BY id DESC LIMIT 5")
            data = cur.fetchall()
    except Exception:
        app.logger.exception("Failed to load environment data")
        flash("Could not load environment data.", "warning")
    return render_template("environment.html", data=data)

@app.route("/feed-schedule")
@login_required
def feed_schedule():
    data = []
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM sensordata1 ORDER BY id DESC LIMIT 5")
            data = cur.fetchall()
    except Exception:
        app.logger.exception("Failed to load feeding data")
        flash("Could not load feeding data.", "warning")
    return render_template("feeding.html", data=data)

@app.route("/sanitization")
@login_required
def sanitization():
    return render_template("sanitization.html")

@app.route("/report")
@login_required
def report():
    return render_template("report.html")

@app.route("/data-table")
@login_required
def data_table():
    data = []
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM sensordata ORDER BY id DESC")
            data = cur.fetchall()
    except Exception:
        app.logger.exception("Failed to fetch data table")
        flash("Could not load data.", "warning")
    return render_template("data_table.html", data=data)

# -------------------------
# Run App
# -------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
