# ChickCare.py
import os
import json
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import firebase_admin
from firebase_admin import credentials, db

# -------------------------
# App Config
# -------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")  # override in Render

# -------------------------
# Firebase Admin SDK
# -------------------------
firebase_json = os.environ.get("FIREBASE_KEY")
if not firebase_json:
    raise RuntimeError("FIREBASE_KEY environment variable not set.")

cred = credentials.Certificate(json.loads(firebase_json))
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://chickencaremonitoringsystem-default-rtdb.firebaseio.com/'
})

# Firebase references
users_ref = db.reference('/users')
sensor_ref = db.reference('/sensordata')
notifications_ref = db.reference('/notifications')

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
        else:
            # Admin static login
            if username.lower() == "admin" and password == "admin":
                session["user_role"] = "admin"
                session["email"] = "admin@domain.com"
                return redirect(url_for("dashboard"))

            # Firebase login
            users = users_ref.order_by_child("Username").equal_to(username).get()
            user = list(users.values())[0] if users else None

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

        users = users_ref.order_by_child("Username").equal_to(username).get()
        if users:
            flash("Username already taken.", "danger")
            return redirect(url_for("register"))

        # Save user to Firebase
        users_ref.push({
            "Email": email,
            "Username": username,
            "Password": password
        })
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
        return [f for f in os.listdir(shots_folder) if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif"))]
    except Exception:
        return []

@app.route("/dashboard")
def dashboard():
    if "user_role" not in session:
        return redirect(url_for("login"))

    # Fetch latest notifications (last 10)
    notifications = notifications_ref.order_by_child("DateTime").limit_to_last(10).get()
    notifications_list = list(notifications.values()) if notifications else []

    # Fetch latest sensor data
    latest_sensor = sensor_ref.order_by_child("DateTime").limit_to_last(1).get()
    latest_sensor_data = list(latest_sensor.values())[0] if latest_sensor else None

    return render_template(
        "dashboard.html",
        image_files=list_shots(),
        notifications=notifications_list,
        data=latest_sensor_data
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
