# ==================================
# 🚨 追記: .env ファイルの読み込み 🚨
# ==================================
from dotenv import load_dotenv
load_dotenv()
# ==================================

# app.py
from flask import Flask, redirect, url_for
from extensions import db  # ✅ ← dbをこちらからimport

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# --- DB設定 ---
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'mysql+pymysql://root:@localhost/ayosuya?unix_socket=/Applications/XAMPP/xamppfiles/var/mysql/mysql.sock'
)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- DB初期化 ---
db.init_app(app)

# --- Blueprintの読み込み ---z
from login import login_bp
from calendar_page import calendar_bp
from insert import insert_bp
from chatbot import chatbot_bp
from shift import shift_bp
from makeshift import makeshift_bp
from line_bot import line_bot_bp

# --- Blueprint登録 ---
app.register_blueprint(login_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(insert_bp)
app.register_blueprint(chatbot_bp)
app.register_blueprint(shift_bp)
app.register_blueprint(makeshift_bp)
app.register_blueprint(line_bot_bp)


@app.route('/')
def index():
    return redirect(url_for('login.login'))

# if __name__ == '__main__':
#     app.run(debug=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
