from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import text
from extensions import db  # ✅ ← 修正ポイント！

insert_bp = Blueprint("insert", __name__, url_prefix="/insert")


@insert_bp.route("/insert", methods=["GET", "POST"])
def insert():
    if request.method == "POST":
        name = request.form["name"]
        password = request.form["password"]
        store_id = request.form["store_id"]

        sql = text("INSERT INTO account (name, password, store_id) VALUES (:name, :password, :store_id)")
        db.session.execute(sql, {"name": name, "password": password, "store_id": store_id})
        db.session.commit()


        flash("従業員を登録しました！", "success")
        return redirect(url_for("login.login"))

    return render_template("accountinsert.html")
