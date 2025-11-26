from flask import Blueprint, render_template, jsonify, request, redirect, url_for
import mysql.connector
from line_notifier import send_help_request_to_staff
from datetime import datetime, timedelta, time as time_cls, date as date_cls
from ortools.sat.python import cp_model
import random, traceback

# ブループリントの定義
line_bp = Blueprint('line', __name__, url_prefix='/line')


# === ユーティリティ関数 ===

# DB接続
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="ayosuya"
    )

# 時刻フォーマット変換
# === ユーティリティ関数 (修正案) ===
# ... (他のコードはそのまま) ...
# 時刻フォーマット変換
def format_time(value):
    """MySQL TIME型 (timedelta, time, or str) → HH:MM形式に変換"""
    if not value:
        return None
    if isinstance(value, str):
        return value[:5]
    elif hasattr(value, "seconds"): # timedelta の処理
        total_seconds = value.seconds
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"
    # ✅ 追加: datetime.time オブジェクトの場合の処理
    elif isinstance(value, time_cls):
        return value.strftime("%H:%M")
    
    return None
# ... (他のコードはそのまま) ...

# datetime.timeオブジェクトへの変換を保証
def ensure_time_obj(v):
    if isinstance(v, time_cls):
        return v
    if isinstance(v, datetime):
        return v.time()
    if isinstance(v, timedelta):
        base = datetime.min + v
        return base.time()
    if isinstance(v, str):
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(v, fmt).time()
            except ValueError:
                continue
    return datetime.strptime("00:00:00", "%H:%M:%S").time()

# timedelta, time_cls, strをHH:MM:SS文字列に変換
def to_time_str(v):
    if isinstance(v, timedelta):
        total_seconds = int(v.total_seconds())
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        return f"{h:02d}:{m:02d}:00"
    elif isinstance(v, str):
        return v
    elif isinstance(v, time_cls):
        return v.strftime("%H:%M:%S")
    elif isinstance(v, datetime):
        return v.time().strftime("%H:%M:%S")
    else:
        return "00:00:00"

from flask import Blueprint, request, jsonify, render_template


# ==========================================
# 🚑 ヘルプ募集機能 (ワンタップ配信システム)
# ==========================================

@line_bp.route("/api/help/create", methods=["POST"])
def create_help_request():
    """
    店長用: ヘルプ募集を作成し、通知対象（空いているスタッフ）をリストアップするAPI
    """
    data = request.json
    target_date = data.get("date")
    start_time_str = data.get("start_time")
    end_time_str = data.get("end_time")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. 募集データをDBに登録
        cursor.execute("""
            INSERT INTO help_requests (date, start_time, end_time, status)
            VALUES (%s, %s, %s, 'open')
        """, (target_date, start_time_str, end_time_str))
        request_id = cursor.lastrowid
        
        # 2. 【ステップA】「その時間にすでにシフトが入っている人」を除外
        # (shift_table に重複する時間帯があるユーザーIDを取得)
        cursor.execute("""
            SELECT DISTINCT user_id 
            FROM shift_table
            WHERE date = %s
            AND NOT (end_time <= %s OR start_time >= %s) 
        """, (target_date, start_time_str, end_time_str))
        
        # 既にシフトに入っていて忙しいユーザーのIDリスト (文字列に変換して['1002']のようにする)
        busy_users = [str(row['user_id']) for row in cursor.fetchall()]

        # 3. 【ステップB】全ユーザーを抽出
        # ここで line_id が NULL のユーザーも取得し、デバッグログで状態を確認できるようにする
        cursor.execute("SELECT ID, name, line_id FROM account")
        all_staff = cursor.fetchall()
        
        # 4. 【ステップC】通知対象をフィルタリング
        eligible_staff = []
        for staff in all_staff:
            staff_id_str = str(staff['ID'])
                
            # 忙しい人を除外 (IDはDBから数値で返ってくる場合があるため、str()で揃える)
            if staff_id_str in busy_users:
                continue
                
            # LINE ID が設定されている人だけを通知対象とする
            if staff.get('line_id'):
                eligible_staff.append(staff)

        # -----------------------------------------------------------
        # 🚨 デバッグログの出力（強化版） 🚨
        print(f"--- 通知対象スタッフ数: {len(eligible_staff)}人 ---")
        print(f"--- 1. 募集時間と重複しているスタッフ (busy_users): {busy_users}")
        print("--- 2. 全スタッフとLINE IDの有無 ---")
        for staff in all_staff:
            staff_id_str = str(staff['ID'])
            status = "対象外(忙しい)" if staff_id_str in busy_users else ("通知対象" if staff.get('line_id') else "対象外(LINE IDなし)")
            print(f"ID: {staff['ID']}, Name: {staff['name']}, LINE ID: {staff.get('line_id')}, Status: {status}")
        print("-------------------------------------------------")
        # -----------------------------------------------------------

        conn.commit()

        # 5. ターゲットのスタッフにLINE通知を送信
        target_count = 0
        
        # 🚨重要: ここのURLを現在の ngrok URL に書き換えてください！
        current_ngrok_url = "https://jaleesa-waxlike-wilily.ngrok-free.dev" # あなたの ngrok URL に戻してください
        help_url = f"{current_ngrok_url}/makeshift/help/respond/{request_id}"
        
        request_data = {
            "date": target_date,
            "start_time": start_time_str,
            "end_time": end_time_str,
            "request_id": request_id
        }

        for staff in eligible_staff:
            send_help_request_to_staff(
                staff_line_id=staff['line_id'],
                request_data=request_data,
                help_url=help_url,
                staff_name=staff['name'] 
            )
            target_count += 1
        
        conn.commit()


        return jsonify({
            "message": "募集を作成し、通知を送信しました。",
            "request_id": request_id,
            "target_count": target_count
        })

    except Exception as e:
            conn.rollback()
            print("--- ❌ CRITICAL ERROR IN create_help_request ---")
            import traceback
            traceback.print_exc()
            return jsonify({"error": "サーバー内部エラー"}), 500
    finally:
        cursor.close()
        conn.close()


@line_bp.route("/api/help/accept", methods=["POST"])
def accept_help_request():
    """
    スタッフ用: ヘルプに応募するAPI (早い者勝ちロジック)
    POSTデータ: { "request_id": 1, "user_id": 5 }
    """
    data = request.json
    req_id = data.get("request_id")
    user_id = data.get("user_id")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. トランザクション開始
        conn.start_transaction()

        # 2. 【重要】早い者勝ち判定
        # status='open' の場合のみ更新を行う。更新件数が1なら勝ち、0なら既に埋まった。
        cursor.execute("""
            UPDATE help_requests 
            SET status = 'closed', accepted_by = %s
            WHERE id = %s AND status = 'open'
        """, (user_id, req_id))
        
        if cursor.rowcount == 0:
            # 既に他の誰かが埋めてしまった場合
            conn.rollback()
            return jsonify({"status": "failed", "message": "タッチの差で募集が埋まってしまいました🙇‍♂️"}), 409

        # 3. 募集情報を取得して shift_table に確定シフトとして書き込む
        cursor.execute("SELECT date, start_time, end_time FROM help_requests WHERE id = %s", (req_id,))
        req_data = cursor.fetchone()

        cursor.execute("""
            INSERT INTO shift_table (user_id, date, start_time, end_time, type)
            VALUES (%s, %s, %s, %s, 'help')
        """, (user_id, req_data['date'], req_data['start_time'], req_data['end_time']))

        conn.commit()

        return jsonify({
            "status": "success", 
            "message": "シフトが確定しました！ありがとうございます！"
        })

    except Exception as e:
        conn.rollback()
        print("--- ❌ CRITICAL ERROR IN accept_help_request ---")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ==========================================
# 🙋‍♂️ ヘルプ応募画面の表示
# ==========================================
@line_bp.route("/help/respond/<int:request_id>", methods=["GET"]) # 👈 /makeshift を削除済み
def help_respond_page(request_id):
    """
    スタッフ用: ヘルプ募集の詳細を表示し、応募ボタンを提供する画面
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. 募集情報を取得
    try:
        cursor.execute("""
            SELECT * FROM help_requests WHERE id = %s
        """, (request_id,))
        request_data = cursor.fetchone()
    
        if not request_data:
            return "募集が見つかりませんでした。", 404
        
        # 🚨 仮のユーザーIDを設定 (LINE連携実装後に置き換えること)
        # 🚨 注意: 本番環境では、ここでLINE IDなどからユーザーIDを特定する必要があります
        # 例: user_id = get_user_id_from_line_session()
        current_staff_id = 1002 # 仮のID。実際にはセッションや認証から取得

        # 2. 画面をレンダリングして返す
        # 変数名を 'req' としてテンプレートに渡す
        return render_template(
            "help_loading.html", 
            req=request_data, 
            staff_id_for_form=current_staff_id # フォームに渡すスタッフID
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": "サーバー内部エラー"}), 500
    finally:
        cursor.close()
        conn.close()