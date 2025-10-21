from flask import Blueprint, render_template, redirect, url_for, session, request
from sqlalchemy import text
from extensions import db  # ✅ ← appではなく extensions から import

calendar_bp = Blueprint("calendar", __name__, url_prefix="/calendar")

# ==========================
# 🔹 カレンダー画面
# ==========================
@calendar_bp.route("/")
def calendar():
    if "user_id" not in session:
        return redirect(url_for("login.login"))
    return render_template("calendar.html")

# ==========================
# 🔹 管理者用カレンダー画面 (/calendar/admin)
# ==========================
@calendar_bp.route("/admin")
def admin():
    if "user_id" not in session:
        return redirect(url_for("login.login"))
    return render_template("calendar2.html")

# ==========================
# 🔹 希望申請フォーム (/calendar/sinsei/<date>)
# ==========================
@calendar_bp.route("/sinsei/<date>", methods=["GET", "POST"])
def sinsei(date):
    if "user_id" not in session:
        return redirect(url_for("login.login"))

    if request.method == "POST":
        name = request.form.get("name")
        work = request.form.get("work")
        time = request.form.get("time")

        # 時間フォーマット変換
        if "~" in time:
            start_time, end_time = time.split("~")
            start_time = start_time.strip() + ":00"
            end_time = end_time.strip() + ":00"
        else:
            start_time = None
            end_time = None

        # SQLでINSERT実行
        sql = text("""
            INSERT INTO calendar (ID, date, work, start_time, end_time)
            VALUES (:name, :date, :work, :start_time, :end_time)
        """)
        db.session.execute(sql, {
            "name": name,
            "date": date,
            "work": work,
            "start_time": start_time,
            "end_time": end_time
        })
        db.session.commit()

        return redirect(url_for("calendar.calendar"))

    return render_template("sinsei.html", date=date)
