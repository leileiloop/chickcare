from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
import psycopg
from psycopg.rows import dict_row
from werkzeug.security import generate_password_hash, check_password_hash
import os

# -------------------------
# Flask app setup
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "sk-04b6eafca8b7f1a91e6e9d3d8ce8ef2c")

# -------------------------
# Database setup (reference)
# -------------------------
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://chickencaredb_user:77msJKAINcktZbFKBV60sVbWz6TZhi6d@dpg-d43j492dbo4c73alniv0-a.oregon-postgres.render.com/chickencaredb"
)

def get_db():
    return psycopg.connect(DB_URL, row_factory=dict_row)

# -------------------------
# Flask-Mail setup
# -------------------------
app.config.update(
    MAIL_SERVER="smtp.gmail.com",
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME="chickenmonitor1208@gmail.com",
    MAIL_PASSWORD=os.environ.get("SMTP_PASSWORD", "leinadloki012"),
)
mail = Mail(app)
serializer = URLSafeTimedSerializer(app.secret_key)

# -------------------------
# Helper: login required
# -------------------------
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_role" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# -------------------------
# Routes
# -------------------------
@app.route("/")
def home():
    return redirect(url_for("login"))

# -------------------------
# LOGIN
# -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        # SUPER ADMIN LOGIN
        if email == "admin" and password == "admin":
            session["user_role"] = "admin"
            flash("Welcome Super Admin!", "success")
            return redirect(url_for("dashboard"))

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cur.fetchone()

            if user and check_password_hash(user["password"], password):
                session["user_id"] = user["id"]
                session["user_role"] = user["role"]
                flash("Login successful!", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Invalid email or password.", "danger")
                return redirect(url_for("login"))

    return render_template("login.html")

# -------------------------
# REGISTER
# -------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])
        role = "user"

        with get_db() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                    (name, email, password, role),
                )
                conn.commit()
                flash("Registration successful! Please log in.", "success")
                return redirect(url_for("login"))
            except psycopg.errors.UniqueViolation:
                conn.rollback()
                flash("This email is already registered.", "danger")

    return render_template("register.html")

# -------------------------
# DASHBOARD ROUTES
# -------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    if session["user_role"] == "admin":
        return render_template("admin-dashboard.html")
    return render_template("dashboard.html")

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
@login_required
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

# -------------------------
# LOGOUT
# -------------------------
@app.route("/logout")
def logout():
    session.clear()
    flash("You’ve been logged out.", "info")
    return redirect(url_for("login"))

# -------------------------
# FORGOT PASSWORD
# -------------------------
@app.route("/forgot", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cur.fetchone()

        if user:
            token = serializer.dumps(email, salt="reset-password")
            reset_link = url_for("reset_password", token=token, _external=True)
            msg = Message(
                "Password Reset - ChickCare",
                sender="chickenmonitor1208@gmail.com",
                recipients=[email],
            )
            msg.html = render_template("reset_password.html", reset_link=reset_link)
            mail.send(msg)

        flash("If your email is registered, instructions have been sent.", "info")
        return redirect(url_for("login"))

    return render_template("forgot.html")

# -------------------------
# RESET PASSWORD
# -------------------------
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
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET password = %s WHERE email = %s", (new_password, email))
            conn.commit()
        flash("Password reset successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token)

# -------------------------
# RUN APP
# -------------------------
if __name__ == "__main__":
    app.run(debug=True)
