# insert.py
from flask import Blueprint, render_template, request, redirect, flash
import mysql.connector

# Blueprintの作成（名前・ルートプレフィックスを設定）
insert_bp = Blueprint('insert', __name__, url_prefix='/insert')

# 🔧 MySQL接続設定
db_config = {
    'host': 'localhost',
    'user': 'root',  # ← 忘れず追加！
    'password': '',
    'database': 'ayosuya',
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# ------------------------------
# 従業員登録画面
# ------------------------------
@insert_bp.route('/', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']
        kengen = request.form['kengen']
        store_id = request.form['store_id']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO account (name, password, kengen, store_id) VALUES (%s, %s, %s, %s)",
            (name, password, kengen, store_id)
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash('✅ 従業員登録が完了しました！')
        return redirect('/insert')  # ← Blueprint名に合わせる

    return render_template('accountinsert.html')
