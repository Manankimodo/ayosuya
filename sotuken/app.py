from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import warnings

# -------------------------------------------------
# 初期設定
# -------------------------------------------------
warnings.filterwarnings("ignore")

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # セッション用

# -------------------------------------------------
# 🔹 MariaDB接続設定（SQLAlchemy）
# -------------------------------------------------
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'mysql+pymysql://root:@localhost/ayosuya?unix_socket=/Applications/XAMPP/xamppfiles/var/mysql/mysql.sock'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# データベースオブジェクト作成
db = SQLAlchemy(app)

# -------------------------------------------------
# 🔹 各画面（Blueprint）の読み込み
# -------------------------------------------------
from a import login_bp
from calendar_page import calendar_bp 
from insert import insert_bp
from chatbot import faq_bp 

# Blueprint登録
app.register_blueprint(login_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(insert_bp)
app.register_blueprint(faq_bp)

# -------------------------------------------------
# 🔹 トップページ（ルート）
# -------------------------------------------------
@app.route('/')
def index():
    # 最初にログイン画面へ飛ばす
    return redirect(url_for('login.login'))

# -------------------------------------------------
# 🔹 メイン起動
# -------------------------------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
