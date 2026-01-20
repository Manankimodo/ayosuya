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
            positions = request.form.getlist("positions")  # 複数選択されたポジション
            
            if not name:
                flash("名前を入力してください", "danger")
                return redirect(url_for("insert.insert"))
            
            if not positions:
                flash("ポジションを1つ以上選択してください", "danger")
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

            # アカウントを登録
            cursor.execute("""
                INSERT INTO account (login_id, name, password, store_id, role)
                VALUES (%s, %s, %s, %s, %s)
            """, (login_id, name, password, store_id, role))

            # 生成されたアカウントIDを取得
            new_user_id = cursor.lastrowid

            # user_positionsテーブルにポジションを登録
            for position_id in positions:
                cursor.execute("""
                    INSERT INTO user_positions (user_id, position_id)
                    VALUES (%s, %s)
                """, (new_user_id, int(position_id)))

            conn.commit()

            flash(f"✅ 登録完了！ ログインID: {login_id} / パスワード: {password}", "success")

        except mysql.connector.Error as e:
            conn.rollback()
            print(f"登録エラー: {e}")
            
            if "Duplicate entry" in str(e):
                flash("登録エラー: IDが重複しています。", "danger")
            elif "Unknown column" in str(e):
                flash("登録エラー: データベース構造に問題があります。", "danger")
            else:
                flash(f"エラーが発生しました: {e}", "danger")
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for("insert.insert"))

    # GET: ポジション一覧と従業員一覧を取得
    try:
        user_id = session.get("user_id")
        
        # ポジション一覧を取得
        cursor.execute("SELECT * FROM positions ORDER BY id")
        positions = cursor.fetchall()
        
        # 店長の店舗IDを取得
        cursor.execute("""
            SELECT store_id FROM account WHERE id = %s
        """, (user_id,))
        
        manager_info = cursor.fetchone()
        if manager_info:
            store_id = manager_info["store_id"]
            
            # 従業員一覧とポジションを取得
            cursor.execute("""
                SELECT a.id, a.login_id, a.name, a.role, a.store_id, s.store_code
                FROM account a
                LEFT JOIN store s ON a.store_id = s.id
                WHERE a.store_id = %s AND a.role = 'staff'
                ORDER BY a.id DESC
            """, (store_id,))
            
            accounts = cursor.fetchall()
            
            # 各従業員のポジションを取得
            for account in accounts:
                account['store_name'] = account.get('store_code') or '未設定'
                
                # ポジションを取得
                cursor.execute("""
                    SELECT p.name
                    FROM user_positions up
                    JOIN positions p ON up.position_id = p.id
                    WHERE up.user_id = %s
                """, (account['id'],))
                
                position_names = [row['name'] for row in cursor.fetchall()]
                account['positions'] = ', '.join(position_names) if position_names else '未設定'
        else:
            accounts = []
            
    except Exception as e:
        print(f"取得エラー: {e}")
        accounts = []
        positions = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template("accountinsert.html", accounts=accounts, positions=positions)


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
            # フォームから新しい名前とポジションを取得
            new_name = request.form.get("name", "").strip()
            positions = request.form.getlist("positions")  # チェックされたポジションのリスト
            
            print(f"DEBUG 編集: 名前={new_name}, ポジション={positions}")  # デバッグ用
            
            if not new_name:
                flash("名前を入力してください", "danger")
                return redirect(url_for("insert.edit", id=id))
            
            if not positions:
                flash("ポジションを1つ以上選択してください", "danger")
                return redirect(url_for("insert.edit", id=id))
            
            # アカウント情報を更新
            cursor.execute("""
                UPDATE account 
                SET name = %s
                WHERE id = %s AND store_id = %s AND role = 'staff'
            """, (new_name, id, store_id))
            
            # 既存のポジションを全て削除（チェックを外したものも含む）
            cursor.execute("DELETE FROM user_positions WHERE user_id = %s", (id,))
            print(f"DEBUG 削除件数: {cursor.rowcount}")  # デバッグ用
            
            # 新しくチェックされたポジションを追加
            for position_id in positions:
                cursor.execute("""
                    INSERT INTO user_positions (user_id, position_id)
                    VALUES (%s, %s)
                """, (id, int(position_id)))
                print(f"DEBUG 追加: user_id={id}, position_id={position_id}")  # デバッグ用
            
            conn.commit()
            flash("✏️ 従業員情報を更新しました！", "success")
            
            return redirect(url_for("insert.insert"))
        
        # GET: 編集対象の従業員情報とポジションを取得
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
        
        # ポジション一覧を取得
        cursor.execute("SELECT * FROM positions ORDER BY id")
        all_positions = cursor.fetchall()
        
        # 現在選択されているポジションIDを取得
        cursor.execute("""
            SELECT position_id FROM user_positions WHERE user_id = %s
        """, (id,))
        selected_position_ids = [row['position_id'] for row in cursor.fetchall()]
        
        return render_template("accountedit.html", 
                             account=account, 
                             positions=all_positions,
                             selected_positions=selected_position_ids)
        
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
        
        # user_positionsから削除
        cursor.execute("DELETE FROM user_positions WHERE user_id = %s", (id,))
        
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