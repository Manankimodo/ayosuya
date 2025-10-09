from flask import Flask, render_template, request, redirect, url_for, flash, session
import pymysql

app = Flask(__name__)
app.secret_key = 'secretkey'

# MySQL設定（XAMPP）
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'python_fastapi'
}

# ログイン画面表示
@app.route('/', methods=['GET'])
def index():
    return render_template('log.html')

# ログイン処理
@app.route('/login', methods=['POST'])
def login():
    username = request.form['ID']
    password = request.form['password']

    try:
        conn = pymysql.connect(**db_config)
        cur = conn.cursor(pymysql.cursors.DictCursor)
        sql = "SELECT * FROM users WHERE username=%s AND password=%s"
        cur.execute(sql, (username, password))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            session['user_name'] = user['username']
            flash("ログイン成功！", "success")
            return redirect(url_for('calendar'))  # ← カレンダー画面へ遷移（後で定義）
        else:
            flash("IDまたはパスワードが違います。", "error")
            return redirect(url_for('index'))

    except Exception as e:
        flash(f"ログイン中にエラーが発生しました: {str(e)}")
        return redirect(url_for('index'))

# 仮のカレンダー画面
@app.route('/calendar')
def calendar():
    user_name = session.get('user_name', 'ゲスト')
    return f"ようこそ {user_name} さん！"

if __name__ == "__main__":
    app.run(debug=True)



# from flask import Flask, render_template, request, redirect, url_for, flash, session
# import pymysql

# app = Flask(__name__)
# app.secret_key = 'your_secret_key'  # セッション用

# # XAMPPのMySQL接続設定
# db_config = {
#     'host': 'localhost',
#     'user': 'root',
#     'password': '',
#     'database': 'python_fastapi',  # ← ← 半角スペースはダメ！アンダーバーに直してください
#     'cursorclass': pymysql.cursors.DictCursor
# }

# # ログイン処理
# @app.route('/', methods=['GET', 'POST'])
# def index():
#     if request.method == 'POST':
#         email = request.form.get('id')
#         password = request.form.get('password')

#         try:
#             conn = pymysql.connect(**db_config)
#             with conn.cursor() as cur:
#                 sql = "SELECT * FROM users WHERE id = %s AND password = %s"
#                 cur.execute(sql, (ID, password))
#                 user = cur.fetchone()
#             conn.close()

#             if user:
#                 session['user_id'] = user['id']
#                 flash("ログイン成功！", "success")
#                 return redirect(url_for('calendar'))
#             else:
#                 flash("IDまたはパスワードが違います。", "error")
#                 return redirect(url_for('index'))

#         except Exception as e:
#             flash(f"ログイン中にエラーが発生しました: {str(e)}")
#             return redirect(url_for('index'))

#     return render_template('log.html')


# @app.route('/calendar')
# def calendar():
#     if 'user_name' in session:
#         return f"ようこそ {session['user_name']} さん！"
#     else:
#         return redirect(url_for('index'))


# if __name__ == '__main__':
#     app.run(debug=True)




# from flask import Flask, render_template, request, redirect, url_for
# from flask_mysqldb import MySQL
# # import pymysql
# from flask import Flask, render_template, request, redirect, url_for, flash, session


# app = Flask(__name__)

# # XAMPPのMySQL接続設定
# app.config['MYSQL_HOST'] = 'localhost'
# app.config['MYSQL_USER'] = 'root'
# app.config['MYSQL_PASSWORD'] = ''  # XAMPPは通常パスワードなし
# app.config['MYSQL_DB'] = 'python fastapi'  # データベース名

# mysql = MySQL(app)

# #ログイン
# @app.route('/', methods=['GET', 'POST'])
# def index():
#     if request.method == 'POST':
#         email = request.form.get('ID')
#         password = request.form.get('password')

#         try:
#             cur = mysql.connection.cursor()
#             sql = "SELECT * FROM users WHERE ID = %s AND password = %s"
#             cur.execute(sql, (email, password))
#             user = cur.fetchone()
#             cur.close()

#             if user:
#                 session['user_name'] = user['name']
#                 flash("ログイン成功！", "success")
#                 return redirect(url_for('calendar'))  # ← ログイン後にcalendarへ遷移
#             else:
#                 flash("IDまたはパスワードが違います。", "error")
#                 return redirect(url_for('index'))

#         except Exception as e:
#             flash(f"ログイン中にエラーが発生しました: {str(e)}")
#             return redirect(url_for('index'))

#     return render_template('log.html')