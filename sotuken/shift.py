from flask import Blueprint, render_template, redirect, url_for, session, request
from sqlalchemy import text
from extensions import db  # ← extensions.py からdbをimport

shift_bp = Blueprint("shift", __name__, url_prefix="/shift")


# ==========================
# 🔹 カレンダー画面
# ==========================
@shift_bp.route("/")
def calendar():
    if "user_id" not in session:
        return redirect(url_for("login.login"))
    return render_template("calendar.html")


# ==========================
# 🔹 希望申請フォーム
# ==========================
@shift_bp.route("/sinsei/<date>", methods=["GET", "POST"])
def sinsei(date):
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

        return redirect(url_for("shift.calendar"))

    return render_template("sinsei.html", date=date)


# ==========================
# 🔹 FAQ管理画面
# ==========================
@shift_bp.route("/manage")
def manage_faq():
    faqs = db.session.execute(text("SELECT * FROM faqs")).fetchall()
    return render_template("manage_faq.html", faqs=faqs)


# ==========================
# 🔹 FAQ追加
# ==========================
@shift_bp.route("/add_faq", methods=["POST"])
def add_faq():
    question = request.form["question"]
    answer = request.form["answer"]

    db.session.execute(
        text("INSERT INTO faqs (question, answer) VALUES (:q, :a)"),
        {"q": question, "a": answer}
    )
    db.session.commit()
    return redirect(url_for("shift.manage_faq"))


# ==========================
# 🔹 FAQ編集
# ==========================
@shift_bp.route("/edit_faq/<int:id>", methods=["POST"])
def edit_faq(id):
    question = request.form["question"]
    answer = request.form["answer"]

    db.session.execute(
        text("UPDATE faqs SET question=:q, answer=:a WHERE id=:id"),
        {"q": question, "a": answer, "id": id}
    )
    db.session.commit()
    return redirect(url_for("shift.manage_faq"))


# ==========================
# 🔹 FAQ削除
# ==========================
@shift_bp.route("/delete_faq/<int:id>")
def delete_faq(id):
    db.session.execute(text("DELETE FROM faqs WHERE id=:id"), {"id": id})
    db.session.commit()
    return redirect(url_for("shift.manage_faq"))
