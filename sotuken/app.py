# app.py
from flask import Flask, redirect, url_for

# --- 各画面（Blueprint）の読み込み ---
from a import login_bp
from calendar import calendar_bp
from insert import insert_bp
from faq import faq_bp

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # セッション用

# --- Blueprint登録 ---
app.register_blueprint(login_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(insert_bp)
app.register_blueprint(faq_bp)

# --- トップページ（ルート） ---
@app.route('/')
def index():
    # 最初にログイン画面へ飛ばす
    return redirect(url_for('login.login'))

# --- Flask起動 ---
if __name__ == '__main__':
    app.run(debug=True)
