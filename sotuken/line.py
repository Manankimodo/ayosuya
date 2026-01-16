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
# 🚑 ヘルプ募集機能 (ワンタップ配信システム) ★改善版★
# ==========================================

@line_bp.route("/api/help/create", methods=["POST"])
def create_help_request():
    """
    店長用: ヘルプ募集を作成し、通知対象（空いているスタッフ）をリストアップするAPI
    ★改善: position_id を追加して、ポジション指定を可能に★
    """
    data = request.json
    target_date = data.get("date")
    start_time_str = data.get("start_time")
    end_time_str = data.get("end_time")
    position_id = data.get("position_id")  # ★新規追加★

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        conn.start_transaction()

        # 0. 店長のstore_idを取得
        if "user_id" not in session:
            return jsonify({"error": "ログインしてください"}), 401
        
        manager_id = session["user_id"]
        
        cursor.execute("""
            SELECT store_id FROM account WHERE id = %s
        """, (manager_id,))
        manager_data = cursor.fetchone()
        
        if not manager_data or not manager_data['store_id']:
            return jsonify({"error": "店舗情報が見つかりません"}), 400
        
        manager_store_id = manager_data['store_id']
        print(f"📍 店長の店舗ID: {manager_store_id}")

        # ★ポジション名を取得★
        cursor.execute("""
            SELECT name FROM positions WHERE id = %s
        """, (position_id,))
        position_data = cursor.fetchone()
        position_name = position_data['name'] if position_data else "未指定"

        # 1. 募集データをDBに登録（★position_idを追加★）
        cursor.execute("""
            INSERT INTO help_requests (date, start_time, end_time, position_id, status)
            VALUES (%s, %s, %s, %s, 'open')
        """, (target_date, start_time_str, end_time_str, position_id))
        request_id = cursor.lastrowid
        
        # 2. 募集を shift_table に「pending」ステータスで登録
        cursor.execute("""
            INSERT INTO shift_table (user_id, date, start_time, end_time, type)
            VALUES (NULL, %s, %s, %s, 'help_pending')
        """, (target_date, start_time_str, end_time_str))
        help_shift_id = cursor.lastrowid
        
        # 3. 「その時間にすでにシフトが入っている人」を除外（同じ店舗のみ）
        cursor.execute("""
            SELECT DISTINCT s.user_id 
            FROM shift_table s
            JOIN account a ON s.user_id = a.ID
            WHERE s.date = %s
            AND s.user_id IS NOT NULL
            AND a.store_id = %s
            AND NOT (s.end_time <= %s OR s.start_time >= %s) 
        """, (target_date, manager_store_id, start_time_str, end_time_str))
        
        busy_users = [str(row['user_id']) for row in cursor.fetchall()]

        # 4. ★該当ポジションのスキルを持つユーザーのみを抽出★
        cursor.execute("""
            SELECT a.ID, a.name, a.line_id, a.store_id 
            FROM account a
            JOIN user_positions up ON a.ID = up.user_id
            WHERE a.store_id = %s
            AND up.position_id = %s
        """, (manager_store_id, position_id))
        all_staff = cursor.fetchall()
        
        # 5. 通知対象をフィルタリング
        eligible_staff = []
        for staff in all_staff:
            staff_id_str = str(staff['ID'])
                
            if staff_id_str in busy_users:
                continue
                
            if staff.get('line_id'):
                eligible_staff.append(staff)

        print(f"--- 📍 店舗ID {manager_store_id} / ポジション: {position_name} の通知対象スタッフ数: {len(eligible_staff)}人 ---")
        print(f"--- 忙しいスタッフ: {busy_users}")

        # 6. ターゲットのスタッフにLINE通知を送信
        target_count = 0
        
        current_ngrok_url = "https://jaleesa-waxlike-wilily.ngrok-free.dev"
        
        request_data = {
            "date": target_date,
            "start_time": start_time_str,
            "end_time": end_time_str,
            "position_name": position_name,  # ★ポジション名を追加★
            "request_id": request_id
        }

        for staff in eligible_staff:
            # URLにuser_idを含める
            help_url = f"{current_ngrok_url}/line/help/respond/{request_id}?user_id={staff['ID']}"
            
            send_help_request_to_staff(
                staff_line_id=staff['line_id'],
                request_data=request_data,
                help_url=help_url,
                staff_name=staff['name'] 
            )
            target_count += 1
        
        conn.commit()

        return jsonify({
            "message": f"店舗ID {manager_store_id} の {position_name} スタッフに募集を送信しました。",
            "request_id": request_id,
            "help_shift_id": help_shift_id,
            "target_count": target_count,
            "store_id": manager_store_id,
            "position_name": position_name
        })

    except Exception as e:
        conn.rollback()
        print("--- ❌ CRITICAL ERROR IN create_help_request ---")
        traceback.print_exc()
        return jsonify({"error": "サーバー内部エラー"}), 500
    finally:
        cursor.close()
        conn.close()


# デバッグ版: accept_help_request関数

@line_bp.route("/api/help/accept", methods=["POST"])
def accept_help_request():
    """
    ヘルプ応募処理（ハイブリッド案）
    
    処理フロー:
    1. calendarテーブルに出勤可能時間を登録（データ整合性）
    2. shift_tableに確定シフトを作成（即座に確定）
    3. is_locked = 1 で保護（次回auto_calendar時に保持）
    4. 該当ポジションの不足データを削除（表示改善）
    """
    data = request.json
    req_id = data.get("request_id")
    user_id = data.get("user_id")

    print(f"\n========== ヘルプ応募開始（ハイブリッド案） ==========")
    print(f"request_id: {req_id}, user_id: {user_id}")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        conn.start_transaction()

        # ==========================================
        # ステップ1: 早い者勝ち判定
        # ==========================================
        print(f"\n--- ステップ1: 早い者勝ち判定 ---")
        cursor.execute("""
            UPDATE help_requests 
            SET status = 'closed', accepted_by = %s
            WHERE id = %s AND status = 'open'
        """, (user_id, req_id))
        
        if cursor.rowcount == 0:
            conn.rollback()
            print(f"❌ 早い者勝ちで失敗")
            return jsonify({
                "status": "failed", 
                "message": "タッチの差で募集が埋まってしまいました🙇‍♂️"
            }), 409

        print(f"✅ help_requests更新成功")

        # ==========================================
        # ステップ2: 募集情報を取得
        # ==========================================
        print(f"\n--- ステップ2: 募集情報取得 ---")
        cursor.execute("""
            SELECT date, start_time, end_time, position_id 
            FROM help_requests 
            WHERE id = %s
        """, (req_id,))
        req_data = cursor.fetchone()
        print(f"募集データ: 日付={req_data['date']}, 時間={req_data['start_time']}～{req_data['end_time']}")

        # ポジション名を取得
        position_name = "ヘルプ"
        if req_data.get('position_id'):
            cursor.execute("""
                SELECT name FROM positions WHERE id = %s
            """, (req_data['position_id'],))
            position_data = cursor.fetchone()
            position_name = position_data['name'] if position_data else "ヘルプ"
        print(f"ポジション: {position_name}")

        # ==========================================
        # ★ステップ3: calendarテーブル（申請情報）に登録★
        # ==========================================
        print(f"\n--- ステップ3: calendar登録（申請情報の更新） ---")
        
        # 1. 既にその日の申請（calendarレコード）があるか確認
        cursor.execute("""
            SELECT ID, start_time, end_time 
            FROM calendar 
            WHERE ID = %s AND date = %s
        """, (user_id, req_data['date']))
        existing_request = cursor.fetchone()
        
        if existing_request:
            print(f"既存の申請あり: {existing_request['start_time']}～{existing_request['end_time']}")
            
            # 既存の申請時間をヘルプの時間に合わせて拡張、または上書き
            # ここでは「ヘルプの時間も含むように枠を広げる」処理にしています
            cursor.execute("""
                UPDATE calendar 
                SET work = 1,
                    start_time = LEAST(start_time, %s),
                    end_time = GREATEST(end_time, %s)
                WHERE ID = %s AND date = %s
            """, (req_data['start_time'], req_data['end_time'], user_id, req_data['date']))
            print(f"✅ calendar更新: 申請時間をヘルプ枠に合わせて拡張しました")
            
        else:
            # 新規で申請データを作成
            cursor.execute("""
                INSERT INTO calendar (ID, date, work, start_time, end_time)
                VALUES (%s, %s, 1, %s, %s)
            """, (user_id, req_data['date'], req_data['start_time'], req_data['end_time']))
            print(f"✅ calendar新規作成: ヘルプ時間を希望時間として登録しました")

        # ==========================================
        # ★ステップ4: shift_tableに確定シフト作成（ロックなし）★
        # ==========================================
        print(f"\n--- ステップ4: shift_table確定シフト作成 ---")
        
        # 既存の help_pending 枠を埋めるか、新規作成するか
        cursor.execute("""
            SELECT id FROM shift_table
            WHERE date = %s AND start_time = %s AND end_time = %s 
            AND type = 'help_pending' AND user_id IS NULL
        """, (req_data['date'], req_data['start_time'], req_data['end_time']))
        pending_exists = cursor.fetchone()

        # ステップ4: shift_tableに確定シフト作成
        if pending_exists:
            # is_lockedを1に戻す
            cursor.execute("""
                UPDATE shift_table
                SET user_id = %s, type = %s, is_locked = 1
                WHERE id = %s
            """, (user_id, position_name, pending_exists['id']))
        else:
            # is_lockedを1に戻す
            cursor.execute("""
                INSERT INTO shift_table (user_id, date, start_time, end_time, type, is_locked)
                VALUES (%s, %s, %s, %s, %s, 1)
            """, (user_id, req_data['date'], req_data['start_time'], req_data['end_time'], position_name))
        
        print(f"✅ shift_table登録完了（is_locked=0）")

        # ==========================================
        # ★ステップ5: 不足データを削除★
        # ==========================================
        print(f"\n--- ステップ5: 不足データ削除 ---")
        
        # 削除前に確認
        cursor.execute("""
            SELECT id, user_id, type 
            FROM shift_table
            WHERE date = %s 
            AND start_time = %s 
            AND end_time = %s 
            AND CAST(user_id AS SIGNED) < 0
            AND type LIKE %s
        """, (req_data['date'], req_data['start_time'], req_data['end_time'], f'%{position_name}%'))
        shortage_records = cursor.fetchall()
        print(f"削除対象の不足データ: {len(shortage_records)}件")
        
        if shortage_records:
            for record in shortage_records:
                print(f"  - {record['type']}")
        
        # 該当ポジションの不足データを削除（1件のみ）
        cursor.execute("""
            DELETE FROM shift_table
            WHERE date = %s 
            AND start_time = %s 
            AND end_time = %s 
            AND CAST(user_id AS SIGNED) < 0
            AND type LIKE %s
            LIMIT 1
        """, (req_data['date'], req_data['start_time'], req_data['end_time'], f'%{position_name}%'))
        
        deleted_count = cursor.rowcount
        print(f"✅ 削除完了: {deleted_count}件")

        # ==========================================
        # ステップ6: 最終確認
        # ==========================================
        print(f"\n--- ステップ6: 最終確認 ---")
        
        # calendar確認
        cursor.execute("""
            SELECT * FROM calendar 
            WHERE ID = %s AND date = %s
        """, (user_id, req_data['date']))
        final_calendar = cursor.fetchone()
        print(f"calendar: {final_calendar}")
        
        # shift_table確認
        cursor.execute("""
            SELECT s.id, s.user_id, a.name as user_name, 
                   s.start_time, s.end_time, s.type, s.is_locked
            FROM shift_table s
            LEFT JOIN account a ON s.user_id = a.ID
            WHERE s.date = %s 
            AND s.start_time = %s 
            AND s.end_time = %s
            ORDER BY CAST(s.user_id AS SIGNED) DESC
        """, (req_data['date'], req_data['start_time'], req_data['end_time']))
        final_shifts = cursor.fetchall()
        print(f"shift_table:")
        for shift in final_shifts:
            print(f"  - user_id={shift['user_id']}, type={shift['type']}, locked={shift['is_locked']}")

        # ==========================================
        # コミット
        # ==========================================
        conn.commit()
        print(f"\n✅ コミット成功")
        print(f"========== ヘルプ応募完了 ==========\n")

        return jsonify({
            "status": "success", 
            "message": f"シフトが確定しました！\n役割: {position_name}\nありがとうございます！"
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
# 🙋‍♂️ ヘルプ応募画面の表示 ★改善版★
# ==========================================

@line_bp.route("/help/respond/<int:request_id>", methods=["GET"])
def help_respond_page(request_id):
    """
    スタッフ用: ヘルプ募集の詳細を表示し、応募ボタンを提供する画面
    ★改善: position_nameを表示★
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # ★募集データとポジション名を結合して取得★
        cursor.execute("""
            SELECT hr.*, p.name as position_name
            FROM help_requests hr
            LEFT JOIN positions p ON hr.position_id = p.id
            WHERE hr.id = %s
        """, (request_id,))
        request_data = cursor.fetchone()
    
        if not request_data:
            return "募集が見つかりませんでした。", 404
        
        # URLパラメータからuser_idを取得
        current_staff_id = request.args.get('user_id')
        
        if not current_staff_id:
            return "URLが無効です。LINEからのリンクを使用してください。", 400

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

# ==========================================
# 📋 ポジション一覧取得API（ヘルプモーダル用）
# ==========================================

@line_bp.route("/api/positions", methods=["GET"])
def get_positions():
    """
    ポジション一覧を取得するAPI
    ヘルプモーダルのドロップダウンで使用
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, name 
            FROM positions 
            ORDER BY id
        """)
        positions = cursor.fetchall()
        
        return jsonify(positions), 200
    
    except Exception as e:
        print(f"❌ Error getting positions: {e}")
        traceback.print_exc()
        return jsonify({"error": "ポジション取得に失敗しました"}), 500
    
    finally:
        cursor.close()
        conn.close()