from flask import Blueprint, render_template, redirect, url_for, session, request, flash
from sqlalchemy import text
from extensions import db  # ← extensionsからimport

calendar_bp = Blueprint("calendar", __name__, url_prefix="/calendar")

# ==========================
# 🔹 カレンダー画面
# ==========================
@calendar_bp.route("/")
def calendar():
    if "user_id" not in session:
        return redirect(url_for("login.login"))

    user_id = session["user_id"]

    sql = text("SELECT date FROM calendar WHERE ID = :user_id")
    result = db.session.execute(sql, {"user_id": user_id}).fetchall()
    sent_dates = [row[0].strftime("%Y-%m-%d") for row in result]

    return render_template("calendar.html", sent_dates=sent_dates or [])


@calendar_bp.route("/admin") 
def admin(): 
    if "user_id" not in session: return redirect(url_for("login.login")) 
    return render_template("calendar2.html")

# ==========================
# 🔹 希望申請フォーム
# ==========================
@calendar_bp.route("/sinsei/<date>", methods=["GET", "POST"])
def sinsei(date):
    if "user_id" not in session:
        return redirect(url_for("login.login"))

    if request.method == "POST":
        user_id = session["user_id"]
        name = request.form.get("name")
        work = request.form.get("work")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")

        # 出勤不可なら時間はNone
        if work == "0":
            start_time = None
            end_time = None
        else:
            if start_time and not start_time.endswith(":00"):
                start_time += ":00"
            if end_time and not end_time.endswith(":00"):
                end_time += ":00"

        # ✅ すでに同じ日付の申請があるか確認
        check_sql = text("SELECT COUNT(*) FROM calendar WHERE ID = :user_id AND date = :date")
        result = db.session.execute(check_sql, {"user_id": user_id, "date": date}).scalar()

        if result > 0:
            # ✅ 更新
            update_sql = text("""
                UPDATE calendar
                SET work = :work, start_time = :start_time, end_time = :end_time
                WHERE ID = :user_id AND date = :date
            """)
            db.session.execute(update_sql, {
                "user_id": user_id,
                "date": date,
                "work": work,
                "start_time": start_time,
                "end_time": end_time
            })
            flash(f"{date} の希望を更新しました。", "info")
        else:
            # ✅ 新規登録
            insert_sql = text("""
                INSERT INTO calendar (ID, date, work, start_time, end_time)
                VALUES (:user_id, :date, :work, :start_time, :end_time)
            """)
            db.session.execute(insert_sql, {
                "user_id": user_id,
                "date": date,
                "work": work,
                "start_time": start_time,
                "end_time": end_time
            })
            flash(f"{date} の希望を提出しました。", "success")

        db.session.commit()

        return redirect(url_for("calendar.calendar"))

    return render_template("sinsei.html", date=date)
