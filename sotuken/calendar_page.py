from flask import Blueprint, render_template, redirect, url_for, session, request
from sqlalchemy import text
from extensions import db  # ✅ ← appではなく extensions から import

calendar_bp = Blueprint("calendar", __name__, url_prefix="/calendar")

# ==========================
# 🔹 カレンダー画面-----------------------------------------------------------------------------------------
# ==========================
@calendar_bp.route("/")
def calendar():
    if "user_id" not in session:
        return redirect(url_for("login.login"))
     # ✅ データベースから送信済み日付を取得（例）
    sql = text("SELECT date FROM calendar")
    result = db.session.execute(sql).fetchall()
    sent_dates = [row[0].strftime("%Y-%m-%d") for row in result]

    # ✅ これをテンプレートに渡す
    return render_template("calendar.html", sent_dates=sent_dates)

# ==========================
# 🔹 管理者用カレンダー画面 (/calendar/admin)-----------------------------------------------------------------
# ==========================
@calendar_bp.route("/admin")
def admin():
    if "user_id" not in session:
        return redirect(url_for("login.login"))
    return render_template("calendar2.html")

# ==========================
# 🔹 希望申請フォーム (/calendar/sinsei/<date>)--------------------------------------------------------------
# ==========================
@calendar_bp.route("/sinsei/<date>", methods=["GET", "POST"])
def sinsei(date):
    if "user_id" not in session:
        return redirect(url_for("login.login"))

    if request.method == "POST":
        name = request.form.get("name")
        work = request.form.get("work")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")

        # 入力が出勤不可なら時間はNoneにする
        if work == "0":
            start_time = None
            end_time = None
        else:
            # time型に統一（:00をつける必要がない場合は削除OK）
            if start_time:
                start_time += ":00"
            if end_time:
                end_time += ":00"

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

#-----------------------------------------------------------------------------------------------
@calendar_bp.route("/")
def calendarr():
    if "user_id" not in session:
        return redirect(url_for("login.login"))

   
