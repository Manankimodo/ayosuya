from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import text
from app import db  # ← app.pyのdbを使用

login_bp = Blueprint("login", __name__, url_prefix="/login")

# ==========================
# 🔹 ログイン画面
# ==========================
@login_bp.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_id = request.form["user_id"]
        password = request.form["password"]

        sql = text("SELECT * FROM account WHERE ID = :user_id AND password = :password")
        result = db.session.execute(sql, {"user_id": user_id, "password": password}).fetchone()

        if result:
            session["user_id"] = user_id
            flash("ログインに成功しました！", "success")
            return redirect(url_for("calendar.calendar"))
        else:
            flash("IDまたはパスワードが間違っています。", "danger")

    return render_template("login.html")

# ==========================
# 🔹 ログアウト機能
# ==========================
@login_bp.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("ログアウトしました。", "info")
    return redirect(url_for("login.login"))
