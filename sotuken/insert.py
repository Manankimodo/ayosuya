from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import text
from extensions import db

insert_bp = Blueprint("insert", __name__, url_prefix="/insert")

# ===============================
# 🟢 1. 従業員一覧 & 登録画面
# ===============================
@insert_bp.route("/", methods=["GET", "POST"])
def insert():
    if request.method == "POST":
        name = request.form["name"]
        password = request.form["password"]
        store_id = request.form["store_id"]

        sql = text("INSERT INTO account (name, password, store_id) VALUES (:name, :password, :store_id)")
        db.session.execute(sql, {"name": name, "password": password, "store_id": store_id})
        db.session.commit()

        flash("✅ 従業員を登録しました！", "success")
        return redirect(url_for("insert.insert"))

    # 一覧表示
    result = db.session.execute(text("SELECT id, name, password, store_id FROM account"))
    accounts = result.fetchall()
    return render_template("accountinsert.html", accounts=accounts)

# ===============================
# 🟡 2. 更新機能
# ===============================
@insert_bp.route("/update/<int:id>", methods=["GET", "POST"])
def update(id):
    if request.method == "POST":
        name = request.form["name"]
        password = request.form["password"]
        store_id = request.form["store_id"]

        sql = text("""
            UPDATE account 
            SET name = :name, password = :password, store_id = :store_id
            WHERE id = :id
        """)
        db.session.execute(sql, {"name": name, "password": password, "store_id": store_id, "id": id})
        db.session.commit()

        flash("✏️ 従業員情報を更新しました！", "success")
        return redirect(url_for("insert.insert"))

    # 編集フォーム表示用にデータ取得
    sql = text("SELECT * FROM account WHERE id = :id")
    result = db.session.execute(sql, {"id": id}).fetchone()
    return render_template("accountupdate.html", account=result)

# ===============================
# 🔴 3. 削除機能
# ===============================
@insert_bp.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    sql = text("DELETE FROM account WHERE id = :id")
    db.session.execute(sql, {"id": id})
    db.session.commit()
    flash("🗑️ 従業員を削除しました！", "danger")
    return redirect(url_for("insert.insert"))
