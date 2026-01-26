# ==================================
# 🚨 追記: .env ファイルの読み込み 🚨
# ==================================
from dotenv import load_dotenv
load_dotenv()
# =================================
 
from flask import session
from datetime import timedelta, datetime  # ← timedelta と datetime を追加
from sqlalchemy import text  # ← text を追加
 
# app.py
from flask import Flask, redirect, url_for
from extensions import db  # ✅ ← dbをこちらからimport
 
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# ✅ セッション設定を追加
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # HTTPSの場合はTrue
 
# --- DB設定 ---
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'mysql+pymysql://root:@localhost/ayosuya?unix_socket=/Applications/XAMPP/xamppfiles/var/mysql/mysql.sock'
)
 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
 
# --- DB初期化 ---
db.init_app(app)

# --- ✅ context_processor を統合 ---
@app.context_processor
def inject_common_data():
    """全てのテンプレートで共通データを使えるようにする"""
    # ユーザー情報
    user_info = session.get('user', {})
    print("=" * 50)
    print("DEBUG: セッション全体:", dict(session))
    print("DEBUG: user_info:", user_info)
    print("DEBUG: store_id:", user_info.get('store_id', ''))
    print("DEBUG: name:", user_info.get('name', ''))
    
    # 新しいシフト通知の判定
    user_id = session.get("user_id")
    print(f"🔍 DEBUG 1: user_id = {user_id}")
    
    has_new_shift = False
    
    if user_id:
        # 1. ユーザーの店舗IDを取得
        sql_store = text("SELECT store_id FROM account WHERE ID = :user_id")
        user_data = db.session.execute(sql_store, {"user_id": user_id}).fetchone()
        store_id = user_data[0] if user_data else None
        print(f"🔍 DEBUG 3: store_id = {store_id}")

        if store_id:
            # 2. すべての公開済みシフトを取得
            sql_publish = text("""
                SELECT target_month, updated_at 
                FROM shift_publish_status 
                WHERE store_id = :store_id AND is_published = 1
            """)
            published_shifts = db.session.execute(sql_publish, {"store_id": store_id}).fetchall()
            
            print(f"🔍 DEBUG 4: published_shifts = {published_shifts}")
            
            # 3. 各公開済みシフトについて、未読かどうかチェック
            for shift in published_shifts:
                target_month = shift[0]  # 例: '2026-03'
                db_updated_at = shift[1]
                
                # ✅ タイムゾーン情報を削除
                if db_updated_at and hasattr(db_updated_at, 'tzinfo') and db_updated_at.tzinfo is not None:
                    db_updated_at = db_updated_at.replace(tzinfo=None)
                
                # ✅ データベースから最終閲覧時刻を取得
                sql_view = text("""
                    SELECT last_viewed_at FROM shift_view_history
                    WHERE user_id = :user_id AND target_month = :target_month
                """)
                view_result = db.session.execute(sql_view, {
                    "user_id": user_id,
                    "target_month": target_month
                }).fetchone()
                
                last_viewed_at = view_result[0] if view_result else None
                
                # ✅ datetime オブジェクトかどうか確認してからタイムゾーン削除
                if last_viewed_at:
                    if hasattr(last_viewed_at, 'tzinfo') and last_viewed_at.tzinfo is not None:
                        last_viewed_at = last_viewed_at.replace(tzinfo=None)
                
                print(f"🔍 DEBUG 5: 月={target_month}, 更新={db_updated_at}, 閲覧={last_viewed_at}")
                
                # まだ見ていない、または更新後に見ていない
                if not last_viewed_at or db_updated_at > last_viewed_at:
                    has_new_shift = True
                    print(f"🔍 DEBUG 6: {target_month} が未読です")
                    break  # 1つでも未読があればバッジ表示
    
    print(f"🔍 DEBUG 7: has_new_shift = {has_new_shift}")
    print("=" * 50)
    
    return dict(
        store_id=user_info.get('store_id', ''),
        user_name=user_info.get('name', ''),
        has_new_shift=has_new_shift
    )
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
    # ▲▲▲ 追加する魔法のコード(ここまで) ▲▲▲

    # 1行にまとめる(reloaderをTrueにする)
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=True)

# どの画面の render_template でも has_new_shift が使えるようにする