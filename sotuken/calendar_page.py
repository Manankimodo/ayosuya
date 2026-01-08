from flask import Blueprint, render_template, redirect, url_for, session, request, flash, jsonify
from sqlalchemy import text
from extensions import db
import mysql.connector
from datetime import datetime # 日付比較用に必要

calendar_bp = Blueprint("calendar", __name__, url_prefix="/calendar")

# DB接続
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="ayosuya"
    )

# ユーザーのstore_idを取得する関数
def get_user_store_id(user_id):
    """ユーザーのstore_idを取得"""
    sql = text("SELECT store_id FROM account WHERE ID = :user_id")
    result = db.session.execute(sql, {"user_id": user_id}).fetchone()
    return result[0] if result else None

# ==========================
# 🔹 カレンダー画面
# ==========================
@calendar_bp.route("/")
def calendar():
    if "user_id" not in session:
        return redirect(url_for("login.login"))

    user_id = session["user_id"]

    sql = text("SELECT date FROM calendar WHERE ID = :user_id")
    result = db.session.execute(sql, {"user_id": user_id}).fetchall()
    sent_dates = [row[0].strftime("%Y-%m-%d") for row in result]

    return render_template("calendar.html", sent_dates=sent_dates or [])


@calendar_bp.route("/admin") 
def admin(): 
    if "user_id" not in session: return redirect(url_for("login.login")) 
    return render_template("calendar2.html")

# ==========================
# 🔹 希望申請フォーム（自動ロック版）
# ==========================
@calendar_bp.route("/sinsei/<date>", methods=["GET", "POST"])
def sinsei(date):
    # 1. ログイン確認
    if "user_id" not in session:
        return redirect(url_for("login.login"))

    user_id = session["user_id"]
    
    # DB接続
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # ---------------------------------------------------
        # 1. ユーザーの店舗ID(store_id)を取得
        # ---------------------------------------------------
        cursor.execute("SELECT store_id FROM account WHERE ID = %s", (user_id,))
        user_data = cursor.fetchone()
        store_id = user_data["store_id"] if user_data else None

        if not store_id:
            flash("店舗情報が取得できませんでした。", "danger")
            return redirect(url_for("calendar.calendar"))

        # ---------------------------------------------------
        # ★ 変更: 日付による自動ロック判定
        # ---------------------------------------------------
        # A. 店舗の締め切り日設定を取得
        cursor.execute("SELECT deadline_day FROM shift_settings WHERE store_id = %s", (store_id,))
        setting = cursor.fetchone()
        # 設定がなければデフォルトを20日にする
        deadline_day = setting['deadline_day'] if setting and setting['deadline_day'] else 20

        # B. 日付比較ロジック
        today = datetime.now()
        target_date_obj = datetime.strptime(date, "%Y-%m-%d") # 申請しようとしている日
        
        is_locked = False
        
        # 「今日の日付」が「締め切り日」を過ぎている場合 (例: 今日が21日で、締切が20日)
        if today.day > deadline_day:
            # 「今月以前のシフト」ならロックする
            # (例: 1月21日に、1月のシフトをいじるのはNG。2月のシフトはOK)
            if target_date_obj.year < today.year or (target_date_obj.year == today.year and target_date_obj.month <= today.month):
                is_locked = True

        # ---------------------------------------------------
        # 既存のシフト希望データを取得 (初期値表示用)
        # ---------------------------------------------------
        cursor.execute(
            "SELECT * FROM calendar WHERE ID = %s AND date = %s",
            (user_id, date)
        )
        current_data = cursor.fetchone()
        
        if current_data:
            if current_data['start_time']:
                current_data['start_time'] = str(current_data['start_time'])[:5]
            if current_data['end_time']:
                current_data['end_time'] = str(current_data['end_time'])[:5]
            current_data['type'] = str(current_data['work'])

        # ---------------------------------------------------
        # 時間フォーマット整形のヘルパー関数
        # ---------------------------------------------------
        def format_time_str(t_obj):
            if t_obj is None: return None
            s = str(t_obj).strip()
            if ':' in s:
                parts = s.split(':')
                h = parts[0].zfill(2)
                m = parts[1]
                return f"{h}:{m}"
            return s[:5]

        # ---------------------------------------------------
        # 店舗設定時間の取得
        # ---------------------------------------------------
        cursor.execute(
            "SELECT start_time, end_time, min_hours_per_day FROM shift_settings WHERE store_id = %s LIMIT 1",
            (store_id,)
        )
        settings_row = cursor.fetchone()
        
        if settings_row:
            min_hours = float(settings_row['min_hours_per_day']) if settings_row['min_hours_per_day'] is not None else 0
            default_start = format_time_str(settings_row['start_time']) or "09:00"
            default_end = format_time_str(settings_row['end_time']) or "22:00"
        else:
            min_hours = 0
            default_start = "09:00"
            default_end = "22:00"
        
        # 特別時間の取得
        cursor.execute(
            "SELECT start_time, end_time, reason FROM special_hours WHERE store_id = %s AND date = %s",
            (store_id, date)
        )
        special = cursor.fetchone()

        if special:
            start_limit = format_time_str(special['start_time'])
            end_limit = format_time_str(special['end_time'])
            notice = f"⚠️ {special.get('reason', '特別営業')} ({start_limit}〜{end_limit})"
        else:
            start_limit = default_start
            end_limit = default_end
            notice = None

        # ---------------------------------------------------
        # 4. 保存処理 (POST)
        # ---------------------------------------------------
        if request.method == "POST":
            # ★ 変更: 自動ロックされていたらブロック
            if is_locked:
                flash(f"⛔ 今月の提出期限({deadline_day}日)を過ぎているため、変更できません。", "danger")
                return redirect(url_for("calendar.calendar"))

            work = request.form.get("work")
            start_time = request.form.get("start_time")
            end_time = request.form.get("end_time")

            # バリデーション
            if work == "1" and start_time and end_time and min_hours > 0:
                try:
                    start_dt = datetime.strptime(start_time, "%H:%M")
                    end_dt = datetime.strptime(end_time, "%H:%M")
                    diff = (end_dt - start_dt).total_seconds() / 3600
                    if diff < 0: diff += 24
                    
                    if diff < min_hours:
                        flash(f"❌ 希望時間が短すぎます。最低 {min_hours} 時間以上入力してください", "danger")
                        return render_template("sinsei.html", date=date, start_limit=start_limit, end_limit=end_limit, min_hours=min_hours, notice=notice, is_locked=is_locked, current_data=current_data)
                except ValueError:
                    pass

            if work == "0":
                start_time = None
                end_time = None
            else:
                if start_time and len(start_time) == 5: start_time += ":00"
                if end_time and len(end_time) == 5: end_time += ":00"

            # DB保存処理
            check_sql = text("SELECT COUNT(*) FROM calendar WHERE ID = :user_id AND date = :date")
            result = db.session.execute(check_sql, {"user_id": user_id, "date": date}).scalar()

            if result > 0:
                update_sql = text("UPDATE calendar SET work = :work, start_time = :start_time, end_time = :end_time WHERE ID = :user_id AND date = :date")
                db.session.execute(update_sql, {"user_id": user_id, "date": date, "work": work, "start_time": start_time, "end_time": end_time})
                msg = f"{date} の希望を更新しました。"
            else:
                insert_sql = text("INSERT INTO calendar (ID, date, work, start_time, end_time) VALUES (:user_id, :date, :work, :start_time, :end_time)")
                db.session.execute(insert_sql, {"user_id": user_id, "date": date, "work": work, "start_time": start_time, "end_time": end_time})
                msg = f"{date} の希望を提出しました。"

            db.session.commit()
            
            flash(msg, "success")    
            return redirect(url_for("calendar.calendar"))

        # ---------------------------------------------------
        # 5. 画面表示 (GET)
        # ---------------------------------------------------
        return render_template("sinsei.html", 
                            date=date, 
                            start_limit=start_limit,
                            end_limit=end_limit,
                            min_hours=min_hours,
                            notice=notice,
                            is_locked=is_locked, # ★自動ロック判定結果を渡す
                            deadline_day=deadline_day, # ★締め切り日も渡しておくと親切
                            current_data=current_data)
                            
    except Exception as e:
        print(f"Sinsei Error: {e}")
        import traceback
        traceback.print_exc()
        flash("システムエラーが発生しました", "danger")
        return redirect(url_for("calendar.calendar"))
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# ==========================
# 🔹 確定シフト確認へのリダイレクト
# ==========================
@calendar_bp.route("/my_confirmed_shift")
def my_confirmed_shift():
    if "user_id" not in session:
        return redirect(url_for("login.login"))
    user_id = session["user_id"]
    return redirect(url_for("makeshift.show_user_shift_view", user_id=user_id))

# ==========================
# 🔹 店長のヘルプ希望申請 (変更なし)
# ==========================
@calendar_bp.route("/manager_help_request")
def manager_help_request():
    if "user_id" not in session:
        return redirect(url_for("login.login"))

    user_id = session["user_id"]
    sql = text("SELECT date FROM calendar WHERE ID = :user_id")
    result = db.session.execute(sql, {"user_id": user_id}).fetchall()
    sent_dates = [row[0].strftime("%Y-%m-%d") for row in result]
    return render_template("manager_help_request.html", sent_dates=sent_dates or [])

@calendar_bp.route("/manager_help_sinsei/<date>", methods=["GET", "POST"])
def manager_help_sinsei(date):
    """店長用: ヘルプ希望申請フォーム"""
    if "user_id" not in session:
        return redirect(url_for("login.login"))

    user_id = session["user_id"]
    store_id = get_user_store_id(user_id)
    if not store_id:
        flash("❌ 店舗情報が取得できませんでした。", "danger")
        return redirect(url_for("calendar.manager_help_request"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT min_hours_per_day FROM shift_settings WHERE store_id = %s LIMIT 1",
        (store_id,)
    )
    settings_row = cursor.fetchone()
    
    if settings_row and settings_row['min_hours_per_day'] is not None:
        min_hours = float(settings_row['min_hours_per_day'])
    else:
        min_hours = 0
    cursor.close()
    conn.close()

    if request.method == "POST":
        work = request.form.get("work")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")

        if work == "0":
            start_time = None
            end_time = None
        else:
            if start_time and not start_time.endswith(":00"): start_time += ":00"
            if end_time and not end_time.endswith(":00"): end_time += ":00"

        check_sql = text("SELECT COUNT(*) FROM calendar WHERE ID = :user_id AND date = :date")
        result = db.session.execute(check_sql, {"user_id": user_id, "date": date}).scalar()

        if result > 0:
            update_sql = text("UPDATE calendar SET work = :work, start_time = :start_time, end_time = :end_time WHERE ID = :user_id AND date = :date")
            db.session.execute(update_sql, {"user_id": user_id, "date": date, "work": work, "start_time": start_time, "end_time": end_time})
            flash(f"{date} のヘルプ希望を更新しました。", "info")
        else:
            insert_sql = text("INSERT INTO calendar (ID, date, work, start_time, end_time) VALUES (:user_id, :date, :work, :start_time, :end_time)")
            db.session.execute(insert_sql, {"user_id": user_id, "date": date, "work": work, "start_time": start_time, "end_time": end_time})
            flash(f"{date} のヘルプ希望を提出しました。", "success")

        db.session.commit()
        return redirect(url_for("calendar.manager_help_request"))

    return render_template("manager_help_sinsei.html", date=date, min_hours=min_hours)


@calendar_bp.route('/update_shift', methods=['POST'])
def update_shift():
    if "user_id" not in session:
        return jsonify({"status": "error", "message": "ログインしてください"}), 401

    user_store_id = session.get('store_id')
    if not user_store_id:
        user_store_id = get_user_store_id(session["user_id"])
        
    target_date_str = request.form.get('date')
    if not target_date_str:
        return jsonify({"status": "error", "message": "日付が必要です"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ★ 変更: API側も自動ロック判定に統一
    cursor.execute("SELECT deadline_day FROM shift_settings WHERE store_id = %s", (user_store_id,))
    setting = cursor.fetchone()
    deadline_day = setting['deadline_day'] if setting and setting['deadline_day'] else 20
    
    cursor.close()
    conn.close()
    
    today = datetime.now()
    target_date_obj = datetime.strptime(target_date_str, "%Y-%m-%d")

    # 締め切り日を過ぎていて、かつ対象が今月以前ならエラー
    if today.day > deadline_day:
        if target_date_obj.year < today.year or (target_date_obj.year == today.year and target_date_obj.month <= today.month):
             return jsonify({"status": "error", "message": f"締め切り日({deadline_day}日)を過ぎているため変更できません"}), 403
    
    return jsonify({"status": "success", "message": "保存可能です"})