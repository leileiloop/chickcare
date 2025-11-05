from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
import os
from functools import wraps

# DB libs
import psycopg  # core psycopg3
from psycopg.rows import dict_row

# Try to import the pool helper from the recommended package; fall back gracefully if not present.
try:
    # recommended separate package that provides a connection pool for psycopg3
    from psycopg_pool import ConnectionPool
    POOL_AVAILABLE = True
except Exception:
    # older import pattern (some examples show psycopg.pool) — but use psycopg_pool when possible.
    ConnectionPool = None
    POOL_AVAILABLE = False

# -------------------------
# Flask app setup
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")

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
if not DB_URL_RAW.startswith("postgresql://"):
    DB_URL = DB_URL_RAW.replace("postgres://", "postgresql://", 1) if DB_URL_RAW.startswith("postgres://") else f"postgresql://{DB_URL_RAW}"
else:
    DB_URL = DB_URL_RAW

# Optional: production session cookie hardening (can be toggled via env if necessary)
app.config.setdefault("SESSION_COOKIE_SECURE", os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true")
app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")

# -------------------------
# Database setup (Connection Pooling with fallback)
# -------------------------
pool = None
if POOL_AVAILABLE and ConnectionPool is not None:
    try:
        # psycopg_pool.ConnectionPool takes a DSN string. Adjust sizes as needed.
        pool = ConnectionPool(conninfo=DB_URL, min_size=1, max_size=10)
        app.logger.info("Database connection pool created successfully (psycopg_pool).")
    except Exception as e:
        app.logger.error(f"Failed to create ConnectionPool: {e}")
        pool = None

if pool is None:
    # Fallback: no pool — create a small helper that opens connections on demand.
    app.logger.warning("psycopg_pool not available or pool creation failed — falling back to connect-on-demand (no pooling). "
                       "Install psycopg[binary,pool] (or psycopg_pool) for connection pooling.")
    def get_conn():
        """Return a new psycopg connection (caller should close or use context manager)."""
        # we set row_factory= dict_row by passing it in connect kwargs
        return psycopg.connect(DB_URL, row_factory=dict_row)
else:
    def get_conn_from_pool():
        """
        Use with: `with get_conn_from_pool() as conn: ...`
        This will yield a connection object and ensure it is returned to pool.
        """
        return pool.connection()

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
        if "user_role" not in session:
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
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        try:
            if pool:
                # use pooled connection
                with get_conn_from_pool() as conn:
                    # ensure row factory is dict for this connection
                    conn.row_factory = dict_row
                    with conn.cursor() as cur:
                        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                        user = cur.fetchone()
            else:
                # connect on demand
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                        user = cur.fetchone()
        except psycopg.Error as e:
            app.logger.exception("Database error during login")
            flash("Database error. Please try again later.", "danger")
            return redirect(url_for("login"))

        if user and "password" in user and psycopg.compat_str and user.get("password") is not None:
            # use werkzeug security check (imported previously in your original code)
            # but import here to avoid unused import earlier if you removed it
            from werkzeug.security import check_password_hash
            if check_password_hash(user["password"], password):
                session["user_id"] = user["id"]
                session["user_role"] = user.get("role", "user")
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
        from werkzeug.security import generate_password_hash
        password = generate_password_hash(raw_password)
        role = "user"

        try:
            if pool:
                with get_conn_from_pool() as conn:
                    conn.row_factory = dict_row
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                            (name, email, password, role),
                        )
                        conn.commit()
            else:
                with get_conn() as conn:
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
            app.logger.exception("Database error during registration")
            flash("Database error. Please try again later.", "danger")

    return render_template("register.html")

# DASHBOARD (for regular users)
@app.route("/dashboard")
@login_required
def dashboard():
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
@admin_required
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
        email = request.form.get("email", "").strip()
        user = None
        try:
            if pool:
                with get_conn_from_pool() as conn:
                    conn.row_factory = dict_row
                    with conn.cursor() as cur:
                        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                        user = cur.fetchone()
            else:
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                        user = cur.fetchone()
        except psycopg.Error:
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
            # Use a dedicated email template (reset_email.html) so the page template and email template don't collide.
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
        from werkzeug.security import generate_password_hash
        new_password = generate_password_hash(new_password_raw)
        try:
            if pool:
                with get_conn_from_pool() as conn:
                    conn.row_factory = dict_row
                    with conn.cursor() as cur:
                        cur.execute("UPDATE users SET password = %s WHERE email = %s", (new_password, email))
                        conn.commit()
            else:
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE users SET password = %s WHERE email = %s", (new_password, email))
                        conn.commit()
            flash("Password reset successful! Please log in.", "success")
        except psycopg.Error:
            app.logger.exception("Database error during password reset")
            flash("Database error. Please try again later.", "danger")
        return redirect(url_for("login"))

    # Render a page that posts the new password (reset_password.html)
    return render_template("reset_password.html", token=token)

# -------------------------
# RUN APP (only for local dev)
# -------------------------
if __name__ == "__main__":
    # In production on Render the webserver (gunicorn) runs the app; don't enable debug there.
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
