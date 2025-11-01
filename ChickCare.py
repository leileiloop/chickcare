# ChickCare.py
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import firebase_admin
from firebase_admin import credentials, db

# -------------------------
# App Config
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# -------------------------
# Firebase Config
# -------------------------
# Use service account JSON stored in environment variable
FIREBASE_CREDENTIALS = os.environ.get("FIREBASE_CREDENTIALS_JSON")

if not FIREBASE_CREDENTIALS:
    raise RuntimeError("FIREBASE_CREDENTIALS_JSON not set in environment variables.")

cred = credentials.Certificate(eval(FIREBASE_CREDENTIALS))
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://chickencaremonitoringsystem-default-rtdb.firebaseio.com/"
})

# -------------------------
# Helper Functions
# -------------------------
def get_user(username):
    users_ref = db.reference("users")
    users = users_ref.get() or {}
    for uid, u in users.items():
        if u.get("Username") == username:
            return u
    return None

def add_user(email, username, password):
    users_ref = db.reference("users")
    return users_ref.push({
        "Email": email,
        "Username": username,
        "Password": password
    })

def get_latest_sensor():
    sensordata_ref = db.reference("sensordata")
    all_data = sensordata_ref.order_by_child("DateTime").get() or {}
    if not all_data:
        return None
    latest_key = max(all_data, key=lambda k: all_data[k]["DateTime"])
    return all_data[latest_key]

def get_notifications(limit=10):
    notif_ref = db.reference("notifications")
    all_notif = notif_ref.order_by_child("DateTime").get() or {}
    sorted_keys = sorted(all_notif, key=lambda k: all_notif[k]["DateTime"], reverse=True)
    return [all_notif[k] for k in sorted_keys[:limit]]

# -------------------------
# Auth Routes
# -------------------------
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            error = "Please provide username and password."
        elif username.lower() == "admin" and password == "admin":
            session["user_role"] = "admin"
            session["email"] = "admin@domain.com"
            return redirect(url_for("dashboard"))
        else:
            user = get_user(username)
            if user and user.get("Password") == password:
                session["user_role"] = "user"
                session["email"] = user.get("Email")
                return redirect(url_for("dashboard"))
            else:
                error = "Invalid credentials."

    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not email or not username or not password:
            flash("Please fill all fields.", "warning")
            return redirect(url_for("register"))

        if get_user(username):
            flash("Username already taken.", "danger")
        else:
            add_user(email, username, password)
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))

# -------------------------
# Dashboard
# -------------------------
def list_shots():
    shots_folder = os.path.join(app.static_folder, "shots")
    try:
        return [f for f in os.listdir(shots_folder) if f.lower().endswith((".jpg",".jpeg",".png",".gif"))]
    except Exception:
        return []

@app.route("/dashboard")
def dashboard():
    if "user_role" not in session:
        return redirect(url_for("login"))

    notifications = get_notifications()
    latest_sensor = get_latest_sensor()

    return render_template(
        "dashboard.html",
        image_files=list_shots(),
        notifications=notifications,
        data=latest_sensor
    )

# -------------------------
# Health Check
# -------------------------
@app.route("/health")
def health():
    return jsonify({"status": "ok"})

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
