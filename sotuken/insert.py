from flask import Blueprint, render_template, request, redirect, url_for, flash
import mysql.connector
from flask_login import current_user
import random
import string

insert_bp = Blueprint("insert", __name__, url_prefix="/insert")

# DB接続
def get_db_connection():
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='ayosuya'
    )
    return conn

# 🔹 login_id を自動生成
def generate_login_id(cursor):
    cursor.execute("SELECT MAX(id) AS max_id FROM account")
    row = cursor.fetchone()
    next_id = (row["max_id"] or 0) + 1
    return f"A{next_id:03d}"   # → A001, A002...

# 🔹 ランダムパスワード生成（8桁英数字）
def generate_password(length=8):
    chars = string.ascii_letters + string.digits  # A-Z a-z 0-9
    return ''.join(random.choice(chars) for _ in range(length))

@insert_bp.route("/", methods=["GET", "POST"])
def insert():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        try:
            name = request.form["name"]

            # 🔹 自動生成
            login_id = generate_login_id(cursor)
            password = generate_password()           # ← ランダムへ変更！
            store_id = current_user.store_id         # ログイン者の店舗
            role = "staff"

            cursor.execute("""
                INSERT INTO account (login_id, name, password, store_id, role)
                VALUES (%s, %s, %s, %s, %s)
            """, (login_id, name, password, store_id, role))

            conn.commit()

            flash(f"✅ 登録完了！ ログインID: {login_id} / パスワード: {password}", "success")

        except Exception as e:
            conn.rollback()
            print(f"登録エラー: {e}")
            flash("エラーが発生しました。", "danger")
        finally:
            conn.close()

        return redirect(url_for("insert.insert"))

    # GET: 一覧表示
    cursor.execute("SELECT * FROM account")
    accounts = cursor.fetchall()
    conn.close()
    
    return render_template("accountinsert.html", accounts=accounts)


# ===============================
# 🔴 3. 削除機能
# ===============================
@insert_bp.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM account WHERE id = %s", (id,))
        conn.commit()
        flash("🗑️ 従業員を削除しました！", "danger")
    except Exception as e:
        conn.rollback()
        print(e)
        flash("削除エラーが発生しました", "danger")
    finally:
        conn.close()
        
    return redirect(url_for("insert.insert"))
