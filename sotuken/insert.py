from flask import Blueprint, render_template, request, redirect, url_for, flash
import mysql.connector
import random
import string
from flask_login import current_user
from werkzeug.security import generate_password_hash

insert_bp = Blueprint("insert", __name__, url_prefix="/insert")

# ==========================================
# データベース接続
# ==========================================
def get_db_connection():
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='ayosuya'
    )
    return conn

# ==========================================
# ランダム生成
# ==========================================
def generate_employee_id():
    prefix = "EMP"
    numbers = ''.join(random.choices(string.digits, k=4))
    return prefix + numbers

def generate_unique_employee_id(cursor):
    while True:
        emp_id = generate_employee_id()
        cursor.execute("SELECT 1 FROM account WHERE login_id=%s", (emp_id,))
        if not cursor.fetchone():
            return emp_id

def generate_password(length=8):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))

# ==========================================
# 従業員一覧・登録
# ==========================================
@insert_bp.route("/", methods=["GET", "POST"])
def insert():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("名前は必須です", "danger")
            conn.close()
            return redirect(url_for("insert.insert"))

        try:
            store_id = current_user.store_id
            employee_id = generate_unique_employee_id(cursor)
            password_plain = generate_password()
            password_hash = generate_password_hash(password_plain)

            cursor.execute(
                "INSERT INTO account (login_id, password, name, store_id, role) VALUES (%s, %s, %s, %s, %s)",
                (employee_id, password_hash, name, store_id, "staff")
            )

            conn.commit()
            flash(f"🎉 従業員を登録しました！ 従業員ID: {employee_id} / パスワード（初回のみ）: {password_plain}", "success")

        except Exception as e:
            conn.rollback()
            print(f"登録エラー: {e}")
            flash("登録エラーが発生しました", "danger")
        finally:
            conn.close()

        return redirect(url_for("insert.insert"))

    # GET 一覧
    cursor.execute("SELECT id, login_id, name, store_id, role FROM account")
    accounts = cursor.fetchall()
    conn.close()

    return render_template("accountinsert.html", accounts=accounts)
# ==========================================
# 従業員情報更新
# ==========================================
@insert_bp.route('/update/<int:id>', methods=['GET', 'POST'])
def update(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        password_plain = request.form.get('password', '').strip()
        role = request.form.get('role', 'staff')

        if not name:
            flash("名前は必須です", "danger")
            conn.close()
            return redirect(url_for('insert.update', id=id))

        try:
            if password_plain:
                # パスワード更新があればハッシュ化
                password_hash = generate_password_hash(password_plain)
                cursor.execute("""
                    UPDATE account 
                    SET name=%s, password=%s, role=%s 
                    WHERE id=%s
                """, (name, password_hash, role, id))
            else:
                # パスワード変更なし
                cursor.execute("""
                    UPDATE account 
                    SET name=%s, role=%s 
                    WHERE id=%s
                """, (name, role, id))

            conn.commit()
            flash('✅ 更新しました！', 'success')
            return redirect(url_for('insert.insert'))

        except Exception as e:
            conn.rollback()
            print(f"更新エラー: {e}")
            flash('更新エラーが発生しました', 'danger')
        finally:
            conn.close()

    # GET 時に従業員情報を取得
    cursor.execute("SELECT id, login_id, name, store_id, role FROM account WHERE id=%s", (id,))
    account = cursor.fetchone()
    conn.close()

    if not account:
        flash("従業員が存在しません", "danger")
        return redirect(url_for('insert.insert'))

    return render_template('accountupdate.html', account=account)
@insert_bp.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM account WHERE id=%s", (id,))
        conn.commit()
        flash("🗑️ 従業員を削除しました！", "danger")
    except Exception as e:
        conn.rollback()
        print(e)
        flash("削除エラーが発生しました", "danger")
    finally:
        conn.close()
    return redirect(url_for("insert.insert"))
