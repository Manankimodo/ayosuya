from flask import Flask, render_template, request, redirect, url_for
from flask_mysqldb import MySQL
from flask import Flask, render_template, request, redirect, url_for, flash, session


app = Flask(__name__)

# XAMPPのMySQL接続設定
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''  # XAMPPは通常パスワードなし
app.config['MYSQL_DB'] = 'ayosuya'  # データベース名

mysql = MySQL(app)

#ログイン
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        email = request.form.get('ID')
        password = request.form.get('password')

        try:
            cur = mysql.connection.cursor()
            sql = "SELECT * FROM users WHERE email = %s AND password = %s"
            cur.execute(sql, (email, password))
            user = cur.fetchone()
            cur.close()

            if user:
                session['user_name'] = user['name']
                flash("ログイン成功！", "success")
                return redirect(url_for('calendar'))  # ← ログイン後にcalendarへ遷移
            else:
                flash("IDまたはパスワードが違います。", "error")
                return redirect(url_for('index'))

        except Exception as e:
            flash(f"ログイン中にエラーが発生しました: {str(e)}")
            return redirect(url_for('index'))

    return render_template('login.html')