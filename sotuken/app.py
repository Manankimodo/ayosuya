# ==================================
# 🚨 追記: .env ファイルの読み込み 🚨
# ==================================
from dotenv import load_dotenv
load_dotenv()
# =================================
 
from flask import session
 
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

# --- ✅ context_processor をここに移動 ---
@app.context_processor
def inject_user_info():
    """全てのテンプレートでuser_infoを使えるようにする"""
    user_info = session.get('user', {})
    print("=" * 50)
    print("DEBUG: セッション全体:", dict(session))
    print("DEBUG: user_info:", user_info)
    print("DEBUG: store_id:", user_info.get('store_id', ''))
    print("DEBUG: name:", user_info.get('name', ''))
    print("=" * 50)
    return dict(
        store_id=user_info.get('store_id', ''),
        user_name=user_info.get('name', '')
    )

from datetime import datetime
from sqlalchemy import text
from flask import session

@app.context_processor
def inject_has_new_shift():
    user_id = session.get("user_id")
    print(f"🔍 DEBUG 1: user_id = {user_id}")  # ← 追加
    
    if not user_id:
        print("🔍 DEBUG 2: user_id がないので False を返す")  # ← 追加
        return dict(has_new_shift=False)

    # 1. ユーザーの店舗IDを取得
    sql_store = text("SELECT store_id FROM account WHERE ID = :user_id")
    user_data = db.session.execute(sql_store, {"user_id": user_id}).fetchone()
    store_id = user_data[0] if user_data else None
    print(f"🔍 DEBUG 3: store_id = {store_id}")  # ← 追加

    # 2. 現在の月を自動取得
    target_month = datetime.now().strftime("%Y-%m")
    print(f"🔍 DEBUG 4: target_month = {target_month}")  # ← 追加
    
    sql_publish = text("""
        SELECT is_published, updated_at FROM shift_publish_status 
        WHERE store_id = :store_id AND target_month = :target_month
    """)
    publish_res = db.session.execute(sql_publish, {
        "store_id": store_id, 
        "target_month": target_month
    }).fetchone()
    
    print(f"🔍 DEBUG 5: publish_res = {publish_res}")  # ← 追加

    has_new_shift = False
    if publish_res and publish_res[0] == 1:
        db_updated_at = publish_res[1]
        if db_updated_at and db_updated_at.tzinfo is not None:
            db_updated_at = db_updated_at.replace(tzinfo=None)
            
        last_viewed_at = session.get("last_viewed_at")
        if last_viewed_at and hasattr(last_viewed_at, 'replace'):
             if last_viewed_at.tzinfo is not None:
                last_viewed_at = last_viewed_at.replace(tzinfo=None)

        print(f"🔍 DEBUG 6: db_updated_at = {db_updated_at}")  # ← 追加
        print(f"🔍 DEBUG 7: last_viewed_at = {last_viewed_at}")  # ← 追加
        
        if not last_viewed_at or db_updated_at > last_viewed_at:
            has_new_shift = True

    print(f"🔍 DEBUG 8: has_new_shift = {has_new_shift}")  # ← 追加
    print("=" * 50)  # ← 追加
    return dict(has_new_shift=has_new_shift)
 
# --- Blueprintの読み込み ---
from login import login_bp
from calendar_page import calendar_bp
from insert import insert_bp
from chatbot import chatbot_bp
from shift import shift_bp
from makeshift import makeshift_bp
from line_bot import line_bot_bp
from store_register import store_bp
from line import line_bp

# --- Blueprint登録 ---
app.register_blueprint(login_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(insert_bp)
app.register_blueprint(chatbot_bp)
app.register_blueprint(shift_bp)
app.register_blueprint(makeshift_bp)
app.register_blueprint(line_bot_bp)
app.register_blueprint(store_bp)
app.register_blueprint(line_bp)
 
@app.route('/')
def index():
    return redirect(url_for('login.login'))
 
from flask import send_from_directory
 
# 🚨 app.py に追加する場合の例 🚨
@app.route('/favicon.ico')
def favicon():
    # 'static' フォルダから 'favicon.ico' ファイルを返します
    return send_from_directory(app.root_path, 'static/favicon.ico', mimetype='image/vnd.microsoft.icon')
 
if __name__ == "__main__":
    # app.py の一番下あたり
    print("\n" + "="*30)
    print("🚀 現在登録されているURL一覧:")
    for rule in app.url_map.iter_rules():
        print(f"{rule} -> {rule.endpoint}")
    print("="*30 + "\n")
    # ▲▲▲ 追加する魔法のコード（ここまで） ▲▲▲

    # 1行にまとめる（reloaderをTrueにする）
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=True)

# どの画面の render_template でも has_new_shift が使えるようにする
