from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
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
        # フォームからデータを取得
        login_id = request.form.get('login_id', '').strip()
        password = request.form.get('password', '').strip()
        
        print(f"DEBUG input: ID={login_id}, PW={password}") 

        # 1. 入力チェック
        if not login_id or not password:
            flash("IDとパスワードを入力してください", "danger")
            return render_template("login.html")

        # 2. 変数の初期化
        manager = None
        staff = None

        # ============================
        # ① 店長ログイン (store_code検索)
        # ============================
        sql_manager = text("""
            SELECT a.id as account_id, a.role, a.name, a.store_id, s.store_code
            FROM account a
            JOIN store s ON CAST(a.store_id AS UNSIGNED) = s.id
            WHERE s.store_code = :code AND a.password = :password
        """)

        manager = db.session.execute(
            sql_manager,
            {"code": login_id, "password": password}
        ).fetchone()

        if manager:
            # 一時的にセッションに情報を保存（選択前）
            session['temp_user'] = {
                'id': manager.account_id,
                'role': manager.role,
                'name': manager.name,
                'store_id': manager.store_id
            }
            # 選択画面へリダイレクト
            return redirect(url_for("login.select_role"))

        # ============================
        # ② 従業員ログイン (login_id検索)
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
            # roleがmanagerの場合は選択画面へ
            if staff.role == 'manager':
                session['temp_user'] = {
                    'id': staff.id,
                    'role': staff.role,
                    'name': staff.name,
                    'store_id': staff.store_id
                }
                return redirect(url_for("login.select_role"))
            
            # staffの場合は直接カレンダー画面へ
            session['user'] = {
                'id': staff.id,
                'role': staff.role,
                'name': staff.name,
                'store_id': staff.store_id
            }
            session['user_id'] = staff.id
            session['role'] = staff.role
            session['user_name'] = staff.name  # ★ この行を追加
            session['store_id'] = staff.store_id  # ★ この行も追加
            return redirect(url_for("calendar.calendar"))

        # 3. ログイン失敗
        flash("ログインID または パスワードが間違っています", "danger")

    return render_template("login.html")

## ----------------------------------------------------
## ロール選択画面 (Manager専用)
## ----------------------------------------------------
@login_bp.route('/select_role')
def select_role():
    # temp_userが存在しない場合はログイン画面へ
    if 'temp_user' not in session:
        flash("セッションが切れました。再度ログインしてください", "warning")
        return redirect(url_for("login.login"))
    
    temp_user = session['temp_user']
    
    # managerロールでない場合はエラー
    if temp_user['role'] != 'manager':
        flash("不正なアクセスです", "danger")
        return redirect(url_for("login.login"))
    
    return render_template("select_role.html", user_name=temp_user['name'])

## ----------------------------------------------------
## ロール選択処理
## ----------------------------------------------------
@login_bp.route('/confirm_role', methods=['POST'])
def confirm_role():
    if 'temp_user' not in session:
        flash("セッションが切れました。再度ログインしてください", "warning")
        return redirect(url_for("login.login"))
    
    selected_role = request.form.get('selected_role')
    temp_user = session['temp_user']
    
    # セッションに正式に保存
    session['user'] = temp_user
    session['user_id'] = temp_user['id']
    session['role'] = temp_user['role']  # 元のrole（manager）
    session['selected_role'] = selected_role  # ★ 選択したロールを保存
    session['user_name'] = temp_user['name']  # ★ この行を追加
    session['store_id'] = temp_user['store_id']  # ★ この行も追加
    
    # 一時保存データを削除
    session.pop('temp_user', None)
    
    # 選択に応じて画面遷移
    if selected_role == 'manager':
        flash(f"{temp_user['name']}さん、管理者としてログインしました", "success")
        return redirect(url_for("login.manager_home"))
    elif selected_role == 'staff':
        flash(f"{temp_user['name']}さん、従業員としてログインしました", "success")
        return redirect(url_for("calendar.calendar"))
    else:
        flash("不正な選択です", "danger")
        return redirect(url_for("login.login"))

## ----------------------------------------------------
## 店長ホーム画面
## ----------------------------------------------------
@login_bp.route('/manager/home')
def manager_home():
    # 認証チェック
    if session.get("role") != "manager":
        return redirect(url_for("login.login"))
        
    sent_dates = [] 

    return render_template(
        "calendar2.html", 
        sent_dates=sent_dates
    )

## ----------------------------------------------------
## 従業員ホーム画面
## ----------------------------------------------------
@login_bp.route('/staff/home')
def staff_home():
    # 認証チェック
    if session.get("role") != "staff": 
        return redirect(url_for("login.login")) 
    
    sent_dates = [] 

    return render_template(
        "calendar.html", 
        sent_dates=sent_dates
    )

## ----------------------------------------------------
## ログアウト処理
## ----------------------------------------------------
@login_bp.route('/logout') 
def logout():
    # セッション内の認証情報をクリアする
    session.pop('user_id', None)
    session.pop('role', None)
    session.pop('user', None)
    session.pop('temp_user', None)  # 一時データも削除

    flash("ログアウトしました", "success") 
    
    return redirect(url_for("login.login"))

@login_bp.route('/register_line_id')
def register_line_id():
    """
    LINE ID 登録画面(QRコード表示 + Webhook対応版)
    """
    if "user_id" not in session:
        flash("先にログインしてください", "danger")
        return redirect(url_for("login.login"))
    
    qr_code_url = os.environ.get('LINE_QR_CODE_URL', 
                                  'https://qr-official.line.me/yourchannelid')
    
    return render_template("register_line_id_qr_webhook.html", qr_code_url=qr_code_url)