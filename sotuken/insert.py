from flask import Blueprint, render_template, request, redirect, url_for, flash
import mysql.connector

# Blueprintの定義
insert_bp = Blueprint("insert", __name__, url_prefix="/insert")

# ==========================================
# データベース接続関数
# ==========================================
def get_db_connection():
    conn = mysql.connector.connect(
        host='localhost',
        user='root',        # ← 環境に合わせてください
        password='',        # ← 環境に合わせてください
        database='ayosuya' # ← 環境に合わせてください
    )
    return conn

# ===============================
# 🟢 1. 従業員一覧 & 登録機能 (修正済み)
# ===============================
@insert_bp.route("/", methods=["GET", "POST"])
def insert():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        try:
            # フォームからデータを受け取る
            name = request.form["name"]
            password = request.form["password"]
            store_id = request.form["store_id"]
            
            # ★修正ポイント：チェックされた役割をリストで受け取る
            # 例: ['1', '2'] (ホールとキッチン)
            positions = request.form.getlist('positions') 

            # 1. account テーブルに登録
            cursor.execute(
                "INSERT INTO account (name, password, store_id) VALUES (%s, %s, %s)", 
                (name, password, store_id)
            )
            
            # 2. 今登録した人のIDを取得
            new_user_id = cursor.lastrowid

            # 3. 役割 (user_positions) を登録
            if positions:
                for pid in positions:
                    cursor.execute(
                        "INSERT INTO user_positions (user_id, position_id) VALUES (%s, %s)",
                        (new_user_id, pid)
                    )

            conn.commit()
            flash("✅ 従業員を登録しました！", "success")
        
        except Exception as e:
            conn.rollback()
            print(f"登録エラー: {e}")
            flash("エラーが発生しました。", "danger")
        finally:
            conn.close()

        return redirect(url_for("insert.insert"))

    # --- GET時の処理（一覧表示） ---
    # 登録されている従業員を取得
    cursor.execute("SELECT * FROM account")
    accounts = cursor.fetchall()
    conn.close()
    
    return render_template("accountinsert.html", accounts=accounts)

# ===============================
# 🟡 2. 更新機能 (作成済み)
# ===============================
@insert_bp.route('/update/<int:id>', methods=['GET', 'POST'])
def update(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        try:
            name = request.form['name']
            password = request.form['password']
            store_id = request.form['store_id']
            
            # チェックされた役割を取得
            selected_positions = request.form.getlist('positions') 

            # 1. 基本情報の更新
            cursor.execute("""
                UPDATE account 
                SET name=%s, password=%s, store_id=%s 
                WHERE id=%s
            """, (name, password, store_id, id))

            # 2. 役割の更新（一度削除して再登録）
            cursor.execute("DELETE FROM user_positions WHERE user_id = %s", (id,))
            
            for pid in selected_positions:
                cursor.execute("INSERT INTO user_positions (user_id, position_id) VALUES (%s, %s)", (id, pid))

            conn.commit()
            flash('✅ 更新しました！', "success")
            return redirect(url_for('insert.insert'))

        except Exception as e:
            conn.rollback()
            print(e)
            flash('更新エラーが発生しました', "danger")
        finally:
            conn.close()

    # --- GET時の処理（編集画面表示） ---
    cursor.execute("SELECT * FROM account WHERE id = %s", (id,))
    account = cursor.fetchone()
    
    # 現在の役割を取得してリストにする
    cursor.execute("SELECT position_id FROM user_positions WHERE user_id = %s", (id,))
    rows = cursor.fetchall()
    current_roles = [row['position_id'] for row in rows]

    conn.close()
    
    return render_template('accountupdate.html', account=account, current_roles=current_roles)

# ===============================
# 🔴 3. 削除機能
# ===============================
@insert_bp.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 関連する user_positions も自動で消える設定になっていなければ先に消すのが安全
        cursor.execute("DELETE FROM user_positions WHERE user_id = %s", (id,))
        cursor.execute("DELETE FROM account WHERE id = %s", (id,))
        conn.commit()
        flash("🗑️ 従業員を削除しました！", "danger")
    except Exception as e:
        conn.rollback()
        print(e)
        flash("削除エラーが発生しました", "danger")
    finally:
        conn.close()
        
    return redirect(url_for("insert.insert"))