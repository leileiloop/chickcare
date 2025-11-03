import os
import secrets
import functools
import psycopg
from psycopg.rows import dict_row
from psycopg.errors import UniqueViolation, OperationalError
from flask import Flask, render_template, request, session, flash, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# -------------------------
# App Configuration
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# -------------------------
# PostgreSQL Configuration
# -------------------------
DATABASE_URL = "postgresql://chickencaredb_tnrw_user:S5Bb7GdOT6zDwYZy8uJrI762A8aq7nG4@dpg-d447gopr0fns73fssg5g-a.oregon-postgres.render.com/chickencaredb_tnrw"

def get_db_connection():
    try:
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    except OperationalError as e:
        raise ConnectionError(f"Database connection failed: {e}")

# -------------------------
# Email Configuration
# -------------------------
GMAIL_USER = "chickenmonitor1208@gmail.com"
GMAIL_PASSWORD = "leinadloki012"  # use env variable in production

def send_reset_email(to_email, token):
    reset_link = f"http://localhost:8080/reset_password/{token}"  # replace with your domain
    subject = "Password Reset Instructions"
    body = f"""
    Hi,

    You requested a password reset. Click the link below to reset your password:

    {reset_link}

    If you did not request this, ignore this email.
    """

    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.send_message(msg)
        print(f"Password reset email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")

# -------------------------
# Decorators
# -------------------------
def login_required(role=None):
    def decorator(view):
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if "user_role" not in session:
                flash("You must log in first.", "warning")
                return redirect(url_for("login"))
            if role and session.get("user_role") != role:
                flash("Access denied.", "danger")
                return redirect(url_for("login"))
            return view(**kwargs)
        return wrapped_view
    return decorator

# -------------------------
# Authentication Routes
# -------------------------
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            error = "Provide username and password."
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
                            flash("Login successful.", "success")
                            return redirect(url_for("admin_dashboard") if session["user_role"]=="admin" else url_for("dashboard"))
                        else:
                            error = "Invalid credentials."
            except Exception as e:
                error = f"Login failed: {e}"
                print(f"LOGIN ERROR: {e}")

    return render_template("login.html", error=error)

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
                    # Ensure role column exists
                    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'user'")
                    cur.execute(
                        "INSERT INTO users (Email, Username, Password, role) VALUES (%s, %s, %s, %s)",
                        (email, username, hashed, "user")
                    )
                conn.commit()

            # Auto login after registration
            session.clear()
            session["user_role"] = "user"
            session["email"] = email
            flash("Registration successful. You are now logged in.", "success")
            return redirect(url_for("dashboard"))

        except UniqueViolation:
            flash("Username or email already exists.", "danger")
        except Exception as e:
            flash(f"Registration error: {e}", "danger")
            print(f"REGISTER ERROR: {e}")

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))

# -------------------------
# Password Reset Routes
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
                        token = secrets.token_urlsafe(16)
                        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token TEXT")
                        cur.execute("UPDATE users SET reset_token=%s WHERE Email=%s", (token, email))
                        conn.commit()
                        send_reset_email(email, token)

                    # Always show generic message
                    flash("If registered, password reset instructions have been sent to your email.", "info")
            return redirect(url_for("login"))

        except Exception as e:
            flash(f"Failed to process password reset: {e}", "danger")
            return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")

@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if request.method == "POST":
        new_password = request.form.get("password", "").strip()
        if not new_password:
            flash("Enter a new password.", "warning")
            return redirect(url_for("reset_password", token=token))

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM users WHERE reset_token=%s", (token,))
                    user = cur.fetchone()
                    if user:
                        hashed = generate_password_hash(new_password)
                        cur.execute("UPDATE users SET Password=%s, reset_token=NULL WHERE reset_token=%s", (hashed, token))
                        conn.commit()
                        flash("Password updated successfully. Please login.", "success")
                        return redirect(url_for("login"))
                    else:
                        flash("Invalid or expired token.", "danger")
                        return redirect(url_for("forgot_password"))
        except Exception as e:
            flash(f"Failed to reset password: {e}", "danger")
            return redirect(url_for("forgot_password"))

    return render_template("reset_password.html", token=token)

# -------------------------
# User Dashboard
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
    except Exception as e:
        flash(f"Error fetching dashboard data: {e}", "danger")
        env_data = []
        water_food_data = []

    return render_template("dashboard.html", env_data=env_data, water_food_data=water_food_data)

# -------------------------
# Admin Dashboard
# -------------------------
@app.route("/admin_dashboard")
@login_required(role="admin")
def admin_dashboard():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, Email, Username FROM users ORDER BY id")
                users = cur.fetchall()
                cur.execute("""
                    SELECT DateTime, CONCAT('Water:', Water_Level, ' Food:', Food_Level) AS message
                    FROM sensordata4 ORDER BY DateTime DESC LIMIT 10
                """)
                notifications = cur.fetchall()
    except Exception as e:
        flash(f"Error loading admin dashboard: {e}", "danger")
        users = []
        notifications = []

    return render_template("admin_dashboard.html", users=users, notifications=notifications)

# -------------------------
# Main Entry
# -------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)
