# store_register.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import db
from sqlalchemy import text as sql_text
import random
import string
store_bp = Blueprint("store", __name__, url_prefix="/store")


# ランダム店舗コード生成（例：6桁）
def generate_store_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def generate_employee_id(length=4):
    prefix = "EMP"
    numbers = ''.join(random.choices(string.digits, k=length))
    return prefix + numbers

@store_bp.route("/register", methods=["GET", "POST"])
def register_store():
    if request.method == "POST":
        store_name = request.form.get("store_name")
        open_time = request.form.get("open_time")
        close_time = request.form.get("close_time")

        manager_name = request.form.get("manager_name")
        manager_password = request.form.get("manager_password")

        if not store_name or not manager_name or not manager_password:
            flash("店舗名・店長名・パスワードは必須です。", "danger")
            return render_template("store_register.html")

        # 店舗コード生成
        store_code = generate_store_code()

        # ① 店舗を登録
        result = db.session.execute(
            sql_text("""
                INSERT INTO store (name, open_time, close_time, store_code)
                VALUES (:name, :open, :close, :code)
            """),
            {
                "name": store_name,
                "open": open_time,
                "close": close_time,
                "code": store_code
            }
        )
        db.session.commit()

        store_id = result.lastrowid

        # ② 店長アカウント登録
        login_id = generate_employee_id()  # ここで呼び出すだけ

        db.session.execute(
            sql_text("""
                INSERT INTO account (login_id, name, password, store_id, role)
                VALUES (:login, :name, :pw, :sid, :role)
            """),
            {
                "login": login_id,
                "name": manager_name,
                "pw": manager_password,
                "sid": store_id,
                "role": "manager"
            }
        )
        db.session.commit()

        return redirect(url_for("store.register_done", store_id=store_id))

    return render_template("store_register.html")



@store_bp.route("/register/done")
def register_done():
    store_id = request.args.get("store_id")

    store = db.session.execute(
        sql_text("""
            SELECT id, name, store_code
            FROM store
            WHERE id = :id
        """),
        {"id": store_id}
    ).fetchone()

    return render_template("register_done.html", store=store)
