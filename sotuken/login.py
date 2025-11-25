from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import text
from extensions import db

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
            SELECT a.id as account_id, a.role, s.store_code
            FROM account a
            JOIN store s ON a.store_id = s.id
            WHERE s.store_code = :code AND a.password = :password
        """)

        manager = db.session.execute(
            sql_manager,
            {"code": login_id, "password": password}
        ).fetchone()

        if manager:
            session['user_id'] = manager.account_id
            session['role'] = manager.role
            return redirect(url_for("login.manager_home"))

        # ============================
        # ② 従業員ログイン (ID検索 - 数字の場合のみ)
        # ============================
        if login_id.isdigit():
            sql_staff = text("""
                SELECT id, role
                FROM account
                WHERE id = :id AND password = :password
            """)

            staff = db.session.execute(
                sql_staff,
                {"id": int(login_id), "password": password} # IDはintに変換
            ).fetchone()

            if staff:
                session['user_id'] = staff.id
                session['role'] = staff.role
                return redirect(url_for("login.staff_home"))

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

    flash("ログアウトしました", "success") 
    
    # ログイン画面へリダイレクト
    return redirect(url_for("login.login"))