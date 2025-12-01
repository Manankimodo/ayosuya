from flask import Blueprint, render_template, jsonify, request, redirect, url_for, session
import mysql.connector
from line_notifier import send_help_request_to_staff
from datetime import datetime, timedelta, time as time_cls, date as date_cls
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import traceback

# ブループリントの定義
line_bp = Blueprint('line', __name__, url_prefix='/line')

# LINE Bot 設定
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise ValueError("環境変数 'LINE_ACCESS_TOKEN' または 'LINE_CHANNEL_SECRET' が設定されていません。")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
webhook_handler = WebhookHandler(LINE_CHANNEL_SECRET)

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
def format_time(value):
    """MySQL TIME型 (timedelta, time, or str) → HH:MM形式に変換"""
    if not value:
        return None
    if isinstance(value, str):
        return value[:5]
    elif hasattr(value, "seconds"):
        total_seconds = value.seconds
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"
    elif isinstance(value, time_cls):
        return value.strftime("%H:%M")
    
    return None

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


# ========================================
# 🔗 Webhook エンドポイント
# ========================================

@line_bp.route("/webhook", methods=['POST'])
def webhook():
    """
    LINE Messaging API からのイベント受信
    """
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    try:
        # 署名検証
        webhook_handler.handle(body, signature)
    except InvalidSignatureError:
        print("❌ Invalid signature. Please check your channel access token/channel secret.")
        return jsonify({"status": "error"}), 403
    except Exception as e:
        print(f"❌ Webhook Error: {e}")
        return jsonify({"status": "error"}), 500

    return jsonify({"status": "ok"}), 200


# ========================================
# 📨 メッセージ受信イベントハンドラ
# ========================================

@webhook_handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """
    ユーザーからのテキストメッセージを受信
    LINE User ID を取得して account テーブルに登録
    """
    try:
        line_user_id = event.source.user_id
        user_message = event.message.text
        
        print(f"📨 受信メッセージ - User ID: {line_user_id}, Message: {user_message}")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            # 1. 一時登録テーブルから account_id を取得
            cursor.execute("""
                SELECT account_id FROM line_id_registration_temp
                WHERE line_user_id IS NULL
                AND created_at > DATE_SUB(NOW(), INTERVAL 10 MINUTE)
                ORDER BY created_at DESC
                LIMIT 1
            """)
            temp_record = cursor.fetchone()

            if temp_record:
                account_id = temp_record['account_id']

                # 2. account テーブルに LINE User ID を登録
                cursor.execute("""
                    UPDATE account
                    SET line_id = %s
                    WHERE id = %s
                """, (line_user_id, account_id))

                # 3. 一時テーブルのレコードを削除
                cursor.execute("""
                    DELETE FROM line_id_registration_temp
                    WHERE account_id = %s
                """, (account_id,))

                conn.commit()

                print(f"✅ LINE User ID 登録成功: Account ID {account_id} → {line_user_id}")

                # 4. ユーザーに確認メッセージを送信
                line_bot_api.push_message(
                    to=line_user_id,
                    messages=TextSendMessage(text="✅ LINE ID の登録が完了しました！\n\nこれからヘルプ募集の通知を受け取れます。")
                )

            else:
                print(f"⚠️ 一時登録レコードが見つかりません")
                
                # ユーザーに通知
                line_bot_api.push_message(
                    to=line_user_id,
                    messages=TextSendMessage(text="申し訳ありません。登録期限が切れてしまいました。\nもう一度「LINE ID登録」から始めてください。")
                )

        except Exception as e:
            conn.rollback()
            print(f"❌ LINE ID 登録エラー: {e}")
            traceback.print_exc()

            # エラーメッセージをユーザーに送信
            line_bot_api.push_message(
                to=line_user_id,
                messages=TextSendMessage(text="エラーが発生しました。管理者にお問い合わせください。")
            )

        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        print(f"❌ Handle Message Error: {e}")
        traceback.print_exc()


# ========================================
# 🆕 LINE ID 登録開始ルート（Flask）
# ========================================

@line_bp.route("/start_line_id_registration", methods=['POST'])
def start_line_id_registration():
    """
    スタッフが「LINE ID登録開始」ボタンをクリックした時のルート
    セッションの account_id を一時テーブルに保存
    """
    if "user_id" not in session:
        return jsonify({"status": "error", "message": "ログインしてください"}), 401

    account_id = session["user_id"]

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 既存レコードを削除（同じアカウントが複数回クリックした場合）
        cursor.execute("""
            DELETE FROM line_id_registration_temp
            WHERE account_id = %s
        """, (account_id,))

        # 新しいレコードを作成
        cursor.execute("""
            INSERT INTO line_id_registration_temp (account_id, created_at)
            VALUES (%s, NOW())
        """, (account_id,))

        conn.commit()

        print(f"✅ LINE ID登録開始: Account ID {account_id}")

        return jsonify({
            "status": "success",
            "message": "登録を開始しました。公式LINEに何かメッセージを送ってください。"
        }), 200

    except Exception as e:
        conn.rollback()
        print(f"❌ Error in start_line_id_registration: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": "エラーが発生しました"}), 500

    finally:
        cursor.close()
        conn.close()


# ========================================
# 🔍 LINE ID 登録状況確認ルート
# ========================================

@line_bp.route("/check_line_id_registration", methods=['GET'])
def check_line_id_registration():
    """
    登録完了をチェックするAPI（画面のポーリング用）
    """
    if "user_id" not in session:
        return jsonify({"status": "error", "registered": False}), 401
    
    account_id = session["user_id"]
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT line_id FROM account WHERE id = %s AND line_id IS NOT NULL
        """, (account_id,))
        result = cursor.fetchone()
        
        if result and result['line_id']:
            return jsonify({"status": "success", "registered": True}), 200
        else:
            return jsonify({"status": "pending", "registered": False}), 200
    
    except Exception as e:
        print(f"❌ Error checking registration: {e}")
        return jsonify({"status": "error", "registered": False}), 500
    
    finally:
        cursor.close()
        conn.close()


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
        conn.start_transaction()

        # 1. 募集データをDBに登録
        cursor.execute("""
            INSERT INTO help_requests (date, start_time, end_time, status)
            VALUES (%s, %s, %s, 'open')
        """, (target_date, start_time_str, end_time_str))
        request_id = cursor.lastrowid
        
        # 2. 募集を shift_table に「pending」ステータスで登録
        cursor.execute("""
            INSERT INTO shift_table (user_id, date, start_time, end_time, type)
            VALUES (NULL, %s, %s, %s, 'help_pending')
        """, (target_date, start_time_str, end_time_str))
        help_shift_id = cursor.lastrowid
        
        # 3. 「その時間にすでにシフトが入っている人」を除外
        cursor.execute("""
            SELECT DISTINCT user_id 
            FROM shift_table
            WHERE date = %s
            AND user_id IS NOT NULL
            AND NOT (end_time <= %s OR start_time >= %s) 
        """, (target_date, start_time_str, end_time_str))
        
        busy_users = [str(row['user_id']) for row in cursor.fetchall()]

        # 4. 全ユーザーを抽出
        cursor.execute("SELECT ID, name, line_id FROM account")
        all_staff = cursor.fetchall()
        
        # 5. 通知対象をフィルタリング
        eligible_staff = []
        for staff in all_staff:
            staff_id_str = str(staff['ID'])
                
            if staff_id_str in busy_users:
                continue
                
            if staff.get('line_id'):
                eligible_staff.append(staff)

        print(f"--- 通知対象スタッフ数: {len(eligible_staff)}人 ---")

        # 6. ターゲットのスタッフにLINE通知を送信
        target_count = 0
        
        current_ngrok_url = "https://jaleesa-waxlike-wilily.ngrok-free.dev"
        help_url = f"{current_ngrok_url}/line/help/respond/{request_id}"
        
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
            "help_shift_id": help_shift_id,
            "target_count": target_count
        })

    except Exception as e:
        conn.rollback()
        print("--- ❌ CRITICAL ERROR IN create_help_request ---")
        traceback.print_exc()
        return jsonify({"error": "サーバー内部エラー"}), 500
    finally:
        cursor.close()
        conn.close()


@line_bp.route("/api/help/accept", methods=["POST"])
def accept_help_request():
    """
    スタッフ用: ヘルプに応募するAPI (早い者勝ちロジック)
    """
    data = request.json
    req_id = data.get("request_id")
    user_id = data.get("user_id")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        conn.start_transaction()

        # 1. 【重要】早い者勝ち判定
        cursor.execute("""
            UPDATE help_requests 
            SET status = 'closed', accepted_by = %s
            WHERE id = %s AND status = 'open'
        """, (user_id, req_id))
        
        if cursor.rowcount == 0:
            conn.rollback()
            return jsonify({"status": "failed", "message": "タッチの差で募集が埋まってしまいました🙇‍♂️"}), 409

        # 2. 募集情報を取得
        cursor.execute("SELECT date, start_time, end_time FROM help_requests WHERE id = %s", (req_id,))
        req_data = cursor.fetchone()

        # 3. shift_table の help_pending を確定シフトに更新
        cursor.execute("""
            UPDATE shift_table
            SET user_id = %s, type = 'help'
            WHERE date = %s 
            AND start_time = %s 
            AND end_time = %s 
            AND type = 'help_pending'
            AND user_id IS NULL
            LIMIT 1
        """, (user_id, req_data['date'], req_data['start_time'], req_data['end_time']))

        if cursor.rowcount == 0:
            cursor.execute("""
                INSERT INTO shift_table (user_id, date, start_time, end_time, type)
                VALUES (%s, %s, %s, %s, 'help')
            """, (user_id, req_data['date'], req_data['start_time'], req_data['end_time']))

        # 4. calendar テーブルに出勤情報を登録
        cursor.execute("""
            SELECT ID FROM calendar 
            WHERE ID = %s AND date = %s
        """, (user_id, req_data['date']))
        
        existing_calendar = cursor.fetchone()
        
        if not existing_calendar:
            cursor.execute("""
                INSERT INTO calendar (ID, date, work, start_time, end_time)
                VALUES (%s, %s, 1, %s, %s)
            """, (user_id, req_data['date'], req_data['start_time'], req_data['end_time']))

        conn.commit()

        return jsonify({
            "status": "success", 
            "message": "シフトが確定しました！ありがとうございます！"
        })

    except Exception as e:
        conn.rollback()
        print("--- ❌ CRITICAL ERROR IN accept_help_request ---")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ==========================================
# 🙋‍♂️ ヘルプ応募画面の表示
# ==========================================

@line_bp.route("/help/respond/<int:request_id>", methods=["GET"])
def help_respond_page(request_id):
    """
    スタッフ用: ヘルプ募集の詳細を表示し、応募ボタンを提供する画面
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM help_requests WHERE id = %s
        """, (request_id,))
        request_data = cursor.fetchone()
    
        if not request_data:
            return "募集が見つかりませんでした。", 404
        
        current_staff_id = 1002

        return render_template(
            "help_loading.html", 
            req=request_data, 
            staff_id_for_form=current_staff_id
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "サーバー内部エラー"}), 500
    finally:
        cursor.close()
        conn.close()