from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import text
from extensions import db
import os


# Blueprintの定義
login_bp = Blueprint('login', __name__, url_prefix='/login')

## ----------------------------------------------------
## ユーザーログイン処理
## ----------------------------------------------------
@login_bp.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # フォームからデータを取得 (HTMLのname属性が 'login_id' と 'password' であること)
        login_id = request.form.get('login_id', '').strip()
        password = request.form.get('password', '').strip()
        
        print(f"DEBUG input: ID={login_id}, PW={password}") 

        # 1. 安全装置: 入力チェック
        if not login_id or not password:
            flash("IDとパスワードを入力してください", "danger")
            return render_template("login.html")

        # 2. UnboundLocalError回避のための変数の初期化
        manager = None
        staff = None

        # ============================
        # ① 店長ログイン (store_code検索)
        # ============================
        sql_manager = text("""
            SELECT a.id as account_id, a.role, a.name, a.store_id, s.store_code
            FROM account a
            JOIN store s ON a.store_id = s.id
            WHERE s.store_code = :code AND a.password = :password
        """)

        manager = db.session.execute(
            sql_manager,
            {"code": login_id, "password": password}
        ).fetchone()

        if manager:
            # セッションにユーザー情報を保存
            session['user'] = {
                'id': manager.account_id,
                'role': manager.role,
                'name': manager.name,
                'store_id': manager.store_id  # ← account.store_id を使用
            }
            session['user_id'] = manager.account_id
            session['role'] = manager.role
            return redirect(url_for("login.manager_home"))

        # ============================
        # ② 従業員ログイン (login_id検索 - 英数字対応)
        # ============================
        sql_staff = text("""
            SELECT a.id, a.role, a.name, a.store_id
            FROM account a
            WHERE a.login_id = :login_id AND a.password = :password
        """)

        staff = db.session.execute(
            sql_staff,
            {"login_id": login_id, "password": password}
        ).fetchone()

        if staff:
            # セッションにユーザー情報を保存
            session['user'] = {
                'id': staff.id,
                'role': staff.role,
                'name': staff.name,
                'store_id': staff.store_id  # ← account.store_id を使用
            }
            session['user_id'] = staff.id
            session['role'] = staff.role
            return redirect('/calendar')

        # 3. ログイン失敗
        flash("ログインID または パスワードが間違っています", "danger")

    return render_template("login.html")

## ----------------------------------------------------
## 店長ホーム画面
## ----------------------------------------------------
@login_bp.route('/manager/home')
def manager_home():
    # 認証チェック
    if session.get("role") != "manager":
        return redirect(url_for("login.login"))
        
    # ★ Undefined Error回避: テンプレート(calendar2.html)で使用するデータを渡す
    #   (ここではデータが未定義の場合を想定し、空のリストを渡しています)
    sent_dates = [] 

    return render_template(
        "calendar2.html", 
        sent_dates=sent_dates  # 店長画面
    )

## ----------------------------------------------------
## 従業員ホーム画面
## ----------------------------------------------------
@login_bp.route('/staff/home')
def staff_home():
    # 認証チェック
    if session.get("role") != "staff": 
        return redirect(url_for("login.login")) 
    
    # ★ Undefined Error回避: テンプレート(calendar.html)で使用するデータを渡す
    sent_dates = [] 

    return render_template(
        "calendar.html", 
        sent_dates=sent_dates  # 従業員画面
    )

## ----------------------------------------------------
## ログアウト処理
## ----------------------------------------------------
@login_bp.route('/logout') 
def logout():
    # セッション内の認証情報をクリアする
    session.pop('user_id', None)
    session.pop('role', None)
    session.pop('user', None)  # 追加: ユーザー情報も削除

    flash("ログアウトしました", "success") 
    
    # ログイン画面へリダイレクト
    return redirect(url_for("login.login"))

@login_bp.route('/register_line_id')
def register_line_id():
    """
    LINE ID 登録画面(QRコード表示 + Webhook対応版)
    """
    if "user_id" not in session:
        flash("先にログインしてください", "danger")
        return redirect(url_for("login.login"))
    
    # Messaging API設定のQRコード画像URL
    qr_code_url = os.environ.get('LINE_QR_CODE_URL', 
                                  'https://qr-official.line.me/yourchannelid')
    
    return render_template("register_line_id_qr_webhook.html", qr_code_url=qr_code_url)