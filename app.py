from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
import psycopg
from psycopg.rows import dict_row
from psycopg.pool import ConnectionPool
from werkzeug.security import generate_password_hash, check_password_hash
import os
from functools import wraps

# -------------------------
# Flask app setup
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")

# FIX (Security): Load secrets ONLY from environment variables. 
# Do NOT provide a default value for sensitive keys.
# Your Render environment variables will provide these.
app.secret_key = os.environ["SECRET_KEY"]
DB_URL_RAW = os.environ["DATABASE_URL"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]

# --- FIX: START ---
# This block fixes the "invalid connection option" error
# It ensures the database URL string has the required "postgresql://" prefix.
if not DB_URL_RAW.startswith("postgresql://"):
    DB_URL = f"postgresql://{DB_URL_RAW}"
else:
    DB_URL = DB_URL_RAW
# --- FIX: END ---


# -------------------------
# Database setup (IMPROVEMENT: Connection Pooling)
# -------------------------
# Create one connection pool when the app starts.
# This pool will manage all database connections for efficiency.
try:
    pool = ConnectionPool(conninfo=DB_URL, min_size=2, max_size=10, row_factory=dict_row)
    print("Database connection pool created successfully.")
except Exception as e:
    # IMPROVEMENT: Print the DB_URL that failed, to help debug environment issues.
    print(f"Error creating database connection pool with URL: {DB_URL}. Error: {e}")
    # If the app can't connect to the DB, it shouldn't start.
    raise

# -------------------------
# Flask-Mail setup
# -------------------------
app.config.update(
    MAIL_SERVER="smtp.gmail.com",
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME="chickenmonitor1208@gmail.com",
    MAIL_PASSWORD=SMTP_PASSWORD,  # FIX (Security): Load from env var
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
        if "user_role" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    """Ensures a user is logged in AND has the 'admin' role."""
    @wraps(f)
    @login_required  # Ensures user is logged in first
    def decorated(*args, **kwargs):
        if session.get("user_role") != "admin":
            flash("You do not have permission to access this page.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated

# -------------------------
# ROUTES
# -------------------------
@app.route("/")
def home():
    return redirect(url_for("login"))

# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_role" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        
        # FIX (Security): Removed hardcoded admin backdoor.
        # Admin must log in via the database.
        
        try:
            # IMPROVEMENT: Use the connection pool
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                    user = cur.fetchone()
        
        # IMPROVEMENT: Catch specific database errors
        except psycopg.Error as e:
            flash(f"Database error: {e}", "danger")
            return redirect(url_for("login"))

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_role"] = user["role"]
            flash(f"Welcome, {user['name']}!", "success")
            
            # IMPROVEMENT: Route admin to admin-dashboard
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")

# REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])
        role = "user"  # Default role

        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                        (name, email, password, role),
                    )
                    conn.commit()
            
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        
        except psycopg.errors.UniqueViolation:
            flash("This email is already registered.", "danger")
        except psycopg.Error as e:
            flash(f"Database error: {e}", "danger")

    return render_template("register.html")

# DASHBOARD (for regular users)
@app.route("/dashboard")
@login_required
def dashboard():
    # This is now the main user dashboard
    return render_template("dashboard.html")

# ADMIN DASHBOARD (for admins)
@app.route("/admin-dashboard")
@admin_required  # FIX (Security): Protected this route
def admin_dashboard():
    return render_template("admin-dashboard.html")

@app.route("/main-dashboard")
@login_required
def main_dashboard():
    return render_template("main-dashboard.html")

@app.route("/environment")
@login_required
def environment():
    return render_template("environment.html")

@app.route("/feed")
@login_required
def feed():
    return render_template("feed.html")

@app.route("/growth")
@login_required
def growth():
    return render_template("growth.html")

@app.route("/manage-users")
@admin_required  # FIX (Security): Protected this route
def manage_users():
    return render_template("manage-users.html")

@app.route("/report")
@login_required
def report():
    return render_template("report.html")

@app.route("/sanitization")
@login_required
def sanitization():
    return render_template("sanitization.html")

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
        email = request.form["email"]
        user = None
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                    user = cur.fetchone()
        except psycopg.Error as e:
            flash(f"Database error: {e}", "danger")
            return redirect(url_for("forgot_password"))

        if user:
            token = serializer.dumps(email, salt="reset-password")
            reset_link = url_for("reset_password", token=token, _external=True)
            msg = Message(
                "Password Reset - ChickCare",
                sender="chickenmonitor1208@gmail.com",
                recipients=[email],
            )
            msg.html = render_template("reset_password.html", reset_link=reset_link)
            
            try:
                mail.send(msg)
                flash("If your email is registered, instructions have been sent.", "info")
            except Exception as e:
                flash(f"Mail server error: {e}", "danger")
        else:
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
        new_password = generate_password_hash(request.form["password"])
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE users SET password = %s WHERE email = %s", (new_password, email))
                    conn.commit()
            flash("Password reset successful! Please log in.", "success")
        except psycopg.Error as e:
            flash(f"Database error: {e}", "danger")
        
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token)

# -------------------------
# RUN APP
# -------------------------
if __name__ == "__main__":
    app.run(debug=True)
