from flask import Blueprint, render_template, request, redirect, url_for
from extensions import db
from sqlalchemy import text as sql_text

store_bp = Blueprint("store", __name__, url_prefix="/store")

@store_bp.route("/register", methods=["GET", "POST"])
def register_store():
    if request.method == "POST":
        store_name = request.form["store_name"]
        open_time = request.form.get("open_time")
        close_time = request.form.get("close_time")

        manager_name = request.form["manager_name"]
        manager_password = request.form["manager_password"]

        # ===========================
        # ① 店舗を登録
        # ===========================
        result = db.session.execute(
            sql_text("""
                INSERT INTO store (name, open_time, close_time)
                VALUES (:name, :open, :close)
            """),
            {"name": store_name, "open": open_time, "close": close_time}
        )
        db.session.commit()

        store_id = result.lastrowid  # ← 新しく作った店舗ID

        # ===========================
        # ② 店長アカウントを作成
        # ===========================
        db.session.execute(
            sql_text("""
                INSERT INTO account (name, password, store_id)
                VALUES (:name, :pw, :sid)
            """),
            {
                "name": manager_name,
                "pw": manager_password,
                "sid": store_id
            }
        )
        db.session.commit()

        # 完了ページへ
        return redirect(url_for("store.register_done", store_id=store_id))

    return render_template("store_register.html")


@store_bp.route("/register/done")
def register_done():
    store_id = request.args.get("store_id")
    return render_template("register_done.html", store_id=store_id)
