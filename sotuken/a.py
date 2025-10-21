from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import warnings

# -------------------------------------------------
# 初期設定
# -------------------------------------------------
warnings.filterwarnings("ignore")
app = Flask(__name__)
app.secret_key = "your_secret_key"  # セッション用（任意の文字列）

# ==========================
# 🔹 MariaDB接続設定
# ==========================
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'mysql+pymysql://root:@localhost/ayosuya?unix_socket=/Applications/XAMPP/xamppfiles/var/mysql/mysql.sock'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ==========================
# 🔹 トップページ（ログイン画面）
# ==========================
@app.route("/")
def index():
    return render_template("login.html")

# ==========================
# 🔹 ログイン処理
# ==========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_id = request.form["user_id"]
        password = request.form["password"]

        # データベースからIDとパスワードを照合
        sql = text("SELECT * FROM account WHERE ID = :user_id AND password = :password")
        result = db.session.execute(sql, {"user_id": user_id, "password": password}).fetchone()

        if result:
            session["user_id"] = user_id
            flash("ログインに成功しました！", "success")
            return redirect(url_for("calendar"))
        else:
            flash("IDまたはパスワードが間違っています。", "danger")

    return render_template("login.html")

# ==========================
# 🔹 カレンダー画面（ログイン後）
# ==========================
@app.route("/calendar")
def calendar():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("calendar.html")

# ==========================
# 🔹 ログアウト機能
# ==========================
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("ログアウトしました。", "info")
    return redirect(url_for("login"))

# ==========================
# 🔹 メイン
# ==========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
