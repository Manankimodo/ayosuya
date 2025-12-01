from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import mysql.connector
import random
import string

insert_bp = Blueprint("insert", __name__, url_prefix="/insert")

# DB接続
def get_db_connection():
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='ayosuya',
        unix_socket='/Applications/XAMPP/xamppfiles/var/mysql/mysql.sock'
    )
    return conn

# 🔹 ランダムID生成(6桁英数字)
def generate_login_id(cursor, length=6):
    while True:
        chars = string.ascii_letters + string.digits  # A-Z a-z 0-9
        login_id = ''.join(random.choice(chars) for _ in range(length))
        
        # 既に存在しないか確認
        cursor.execute("SELECT id FROM account WHERE login_id = %s", (login_id,))
        if not cursor.fetchone():
            return login_id

# 🔹 ランダムパスワード生成(8桁英数字)
def generate_password(length=8):
    chars = string.ascii_letters + string.digits  # A-Z a-z 0-9
    return ''.join(random.choice(chars) for _ in range(length))

@insert_bp.route("/", methods=["GET", "POST"])
def insert():
    # 🔴 認証チェック: 店長のみアクセス可能
    if session.get("role") != "manager":
        flash("アクセス権限がありません", "danger")
        return redirect(url_for("login.login"))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            
            if not name:
                flash("名前を入力してください", "danger")
                return redirect(url_for("insert.insert"))

            # 🔹 セッションから店舗IDを取得
            user_id = session.get("user_id")
            
            # 店長のアカウント情報から店舗IDを取得
            cursor.execute("""
                SELECT store_id FROM account WHERE id = %s
            """, (user_id,))
            
            manager_info = cursor.fetchone()
            if not manager_info:
                flash("店舗情報の取得に失敗しました", "danger")
                return redirect(url_for("insert.insert"))
            
            store_id = manager_info["store_id"]

            # 🔹 自動生成
            login_id = generate_login_id(cursor)  # 6桁英数字のID生成
            password = generate_password()        # 8桁英数字のパスワード生成
            role = "staff"

            # login_idとpasswordを登録
            cursor.execute("""
                INSERT INTO account (login_id, name, password, store_id, role)
                VALUES (%s, %s, %s, %s, %s)
            """, (login_id, name, password, store_id, role))

            conn.commit()
            
            # 生成されたIDを取得
            new_id = cursor.lastrowid

            flash(f"✅ 登録完了！ ログインID: {login_id} / パスワード: {password}", "success")

        except mysql.connector.Error as e:
            conn.rollback()
            print(f"登録エラー: {e}")
            
            # エラーメッセージを分かりやすく
            if "Duplicate entry" in str(e):
                flash("登録エラー: IDが重複しています。データベースを確認してください。", "danger")
            elif "Unknown column" in str(e):
                flash("登録エラー: データベース構造に問題があります。", "danger")
            else:
                flash(f"エラーが発生しました: {e}", "danger")
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for("insert.insert"))

    # GET: 一覧表示(同じ店舗の従業員のみ)
    try:
        user_id = session.get("user_id")
        
        # 店長の店舗IDを取得
        cursor.execute("""
            SELECT store_id FROM account WHERE id = %s
        """, (user_id,))
        
        manager_info = cursor.fetchone()
        if manager_info:
            store_id = manager_info["store_id"]
            
            # 🔹 login_idカラムも取得
            cursor.execute("""
                SELECT a.id, a.login_id, a.name, a.role, a.store_id, s.store_code
                FROM account a
                LEFT JOIN store s ON a.store_id = s.id
                WHERE a.store_id = %s AND a.role = 'staff'
                ORDER BY a.id DESC
            """, (store_id,))
            
            accounts = cursor.fetchall()
            
            # store_codeをstore_nameとして表示
            for account in accounts:
                account['store_name'] = account.get('store_code') or '未設定'
        else:
            accounts = []
            
    except Exception as e:
        print(f"取得エラー: {e}")
        accounts = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template("accountinsert.html", accounts=accounts)


# ===============================
# 🔴 編集機能
# ===============================
@insert_bp.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    # 🔴 認証チェック
    if session.get("role") != "manager":
        flash("アクセス権限がありません", "danger")
        return redirect(url_for("login.login"))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 店長の店舗IDを取得
        user_id = session.get("user_id")
        cursor.execute("SELECT store_id FROM account WHERE id = %s", (user_id,))
        manager_info = cursor.fetchone()
        
        if not manager_info:
            flash("権限エラー", "danger")
            return redirect(url_for("insert.insert"))
        
        store_id = manager_info["store_id"]
        
        if request.method == "POST":
            # フォームから新しい名前を取得
            new_name = request.form.get("name", "").strip()
            
            if not new_name:
                flash("名前を入力してください", "danger")
                return redirect(url_for("insert.edit", id=id))
            
            # 同じ店舗の従業員のみ更新可能
            cursor.execute("""
                UPDATE account 
                SET name = %s
                WHERE id = %s AND store_id = %s AND role = 'staff'
            """, (new_name, id, store_id))
            
            if cursor.rowcount > 0:
                conn.commit()
                flash("✏️ 従業員情報を更新しました！", "success")
            else:
                flash("更新対象が見つかりませんでした", "warning")
            
            return redirect(url_for("insert.insert"))
        
        # GET: 編集対象の従業員情報を取得
        cursor.execute("""
            SELECT a.id, a.login_id, a.name, a.role, s.store_code
            FROM account a
            LEFT JOIN store s ON a.store_id = s.id
            WHERE a.id = %s AND a.store_id = %s AND a.role = 'staff'
        """, (id, store_id))
        
        account = cursor.fetchone()
        
        if not account:
            flash("編集対象が見つかりませんでした", "danger")
            return redirect(url_for("insert.insert"))
        
        account['store_name'] = account.get('store_code') or '未設定'
        
        return render_template("accountedit.html", account=account)
        
    except Exception as e:
        print(f"編集エラー: {e}")
        flash("編集エラーが発生しました", "danger")
        return redirect(url_for("insert.insert"))
    finally:
        cursor.close()
        conn.close()


# ===============================
# 🔴 削除機能
# ===============================
@insert_bp.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    # 🔴 認証チェック
    if session.get("role") != "manager":
        flash("アクセス権限がありません", "danger")
        return redirect(url_for("login.login"))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 店長の店舗IDを取得
        user_id = session.get("user_id")
        cursor.execute("SELECT store_id FROM account WHERE id = %s", (user_id,))
        manager_info = cursor.fetchone()
        
        if not manager_info:
            flash("権限エラー", "danger")
            return redirect(url_for("insert.insert"))
        
        store_id = manager_info["store_id"]
        
        # 同じ店舗の従業員のみ削除可能
        cursor.execute("""
            DELETE FROM account 
            WHERE id = %s AND store_id = %s AND role = 'staff'
        """, (id, store_id))
        
        if cursor.rowcount > 0:
            conn.commit()
            flash("🗑️ 従業員を削除しました！", "success")
        else:
            flash("削除対象が見つかりませんでした", "warning")
            
    except Exception as e:
        conn.rollback()
        print(f"削除エラー: {e}")
        flash("削除エラーが発生しました", "danger")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for("insert.insert"))