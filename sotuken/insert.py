from flask import Flask, render_template, request, redirect, flash
import mysql.connector
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # セッション用

# 🔧 MySQL接続設定
db_config = {
    'host': 'localhost',       
    'password': '',
    'database': 'ayosuya',
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

@app.route('/')
def index():
    return redirect('/register')

@app.route('/register', methods=['GET', 'POST'])
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
        return redirect('/register')

    return render_template('accountinsert.html')

if __name__ == '__main__':
    app.run(debug=True)
