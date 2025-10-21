from flask import Blueprint, render_template, redirect, url_for, session

calendar_bp = Blueprint("calendar", __name__, url_prefix="/calendar")

# ==========================
# 🔹 カレンダー画面
# ==========================
@calendar_bp.route("/")
def calendar():
    if "user_id" not in session:
        return redirect(url_for("login.login"))
    return render_template("calendar.html")
