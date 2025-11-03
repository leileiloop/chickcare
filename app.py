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

# Load secret key from environment (fallback for local testing)
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_key")

# -------------------------
# Database setup
# -------------------------
DB_URL = os.environ.get("DATABASE_URL", "postgresql://chickencaredb_user:77msJKAINcktZbFKBV60sVbWz6TZhi6d@dpg-d43j492dbo4c73alniv0-a.oregon-postgres.render.com/chickencaredb")

# -------------------------
# Flask-Mail setup
# -------------------------
app.config.update(
    MAIL_SERVER="smtp.gmail.com",
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME="chickenmonitor1208@gmail.com",
    MAIL_PASSWORD=os.environ.get("SMTP_PASSWORD"),  # secure!
)

mail = Mail(app)
serializer = URLSafeTimedSerializer(app.secret_key)

# -------------------------
# Database helper
# -------------------------
def get_db():
    return psycopg.connect(DB_URL, row_factory=dict_row)

# -------------------------
# Routes
# -------------------------
@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        # Admin check
        if email == "admin" and password == "admin":
            session["user_role"] = "admin"
            return redirect(url_for("dashboard"))

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cur.fetchone()

            if user and check_password_hash(user["password"], password):
                session["user_id"] = user["id"]
                session["user_role"] = user["role"]
                return redirect(url_for("dashboard"))
            else:
                flash("Invalid email or password.", "danger")
                return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])
        role = "user"  # every new registration is user

        with get_db() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                    (name, email, password, role),
                )
                conn.commit()
                flash("Account created successfully! Please login.", "success")
                return redirect(url_for("login"))
            except psycopg.errors.UniqueViolation:
                flash("Email already registered.", "danger")
                conn.rollback()
    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session and session.get("user_role") != "admin":
        flash("Please log in to access dashboard.", "warning")
        return redirect(url_for("login"))

    if session.get("user_role") == "admin":
        return render_template("admin_dashboard.html")
    else:
        return render_template("dashboard.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You’ve been logged out.", "info")
    return redirect(url_for("login"))

# -------------------------
# Forgot Password Flow
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
            link = url_for("reset_password", token=token, _external=True)

            msg = Message(
                "Password Reset Request - ChickCare",
                sender="chickenmonitor1208@gmail.com",
                recipients=[email],
            )
            msg.html = render_template("email_reset.html", reset_link=link)
            mail.send(msg)

        flash("If registered, password reset instructions have been sent.", "info")
        return redirect(url_for("login"))

    return render_template("forgot.html")


@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = serializer.loads(token, salt="reset-password", max_age=3600)
    except (SignatureExpired, BadSignature):
        flash("The reset link is invalid or expired.", "danger")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        new_password = generate_password_hash(request.form["password"])

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET password = %s WHERE email = %s", (new_password, email))
            conn.commit()

        flash("Password updated! You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("reset.html")

# -------------------------
# Run app
# -------------------------
if __name__ == "__main__":
    app.run(debug=True)
