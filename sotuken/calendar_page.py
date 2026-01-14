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
from datetime import datetime

from datetime import datetime

from flask import render_template, session, redirect, url_for, request
from sqlalchemy import text
from datetime import datetime
from dateutil.relativedelta import relativedelta

@calendar_bp.route("/")
def calendar():
    if "user_id" not in session:
        return redirect(url_for("login.login"))

    user_id = session["user_id"]

    # 1. ユーザーの店舗IDを取得
    sql_store = text("SELECT store_id FROM account WHERE ID = :user_id")
    user_data = db.session.execute(sql_store, {"user_id": user_id}).fetchone()
    store_id = user_data[0] if user_data else None

    if not store_id:
        return "店舗情報が見つかりません", 404

    # --- 🌟 2. 募集中のターゲット月を自動計算するロジック ---
    # 設定から締め切り日を取得
    sql_deadline = text("SELECT deadline_day FROM shift_settings WHERE store_id = :store_id")
    setting = db.session.execute(sql_deadline, {"store_id": store_id}).fetchone()
    deadline_day = setting[0] if setting and setting[0] else 20

    today = datetime.now()
    # 今月の締め切り日時（例: 1月13日 23:59:59）
    this_month_deadline = today.replace(day=deadline_day, hour=23, minute=59, second=59)

    if today > this_month_deadline:
        # 期限を過ぎたので「翌々月」を表示 (例: 1/14なら3月分)
        target_month = (today + relativedelta(months=2)).strftime("%Y-%m")
    else:
        # 期限内なので「翌月」を表示 (例: 1/12なら2月分)
        target_month = (today + relativedelta(months=1)).strftime("%Y-%m")

    # --- 🌟 3. グラフに表示するデータをターゲット月に絞って取得 ---
    # ここで target_month を使うことで、期限切れの月のグラフは出なくなります
    sql_shifts = text("""
        SELECT c.*, a.name as user_name 
        FROM calendar c
        JOIN account a ON c.ID = a.ID
        WHERE a.store_id = :store_id 
        AND DATE_FORMAT(c.date, '%Y-%m') = :target_month
    """)
    shift_results = db.session.execute(sql_shifts, {
        "store_id": store_id, 
        "target_month": target_month
    }).fetchall()

    # JavaScript (Chart.js) が読める形式に変換
    shifts_for_js = []
    for s in shift_results:
        shifts_for_js.append({
            "user_id": s.ID,
            "user_name": s.user_name,
            "date": s.date.strftime("%Y-%m-%d"),
            "start_time": str(s.start_time)[:5] if s.start_time else "00:00",
            "end_time": str(s.end_time)[:5] if s.end_time else "00:00",
            "type": "出勤" if s.work == 1 else "休み"
        })

    # 4. 希望日リスト取得（ドット表示用などは全期間でもOKですが、月を絞るならここも調整）
    sql_dates = text("SELECT date FROM calendar WHERE ID = :user_id")
    result = db.session.execute(sql_dates, {"user_id": user_id}).fetchall()
    sent_dates = [row[0].strftime("%Y-%m-%d") for row in result]

    # 5. シフトの公開状態と通知判定 (target_monthと連動)
    sql_publish = text("""
        SELECT is_published, updated_at FROM shift_publish_status 
        WHERE store_id = :store_id AND target_month = :target_month
    """)
    publish_res = db.session.execute(sql_publish, {
        "store_id": store_id, 
        "target_month": target_month
    }).fetchone()
    
    has_new_shift = False
    if publish_res and publish_res[0] == 1:
        db_updated_at = publish_res[1].replace(tzinfo=None) if publish_res[1] else None
        last_viewed_at = session.get("last_viewed_at")
        if last_viewed_at:
            last_viewed_at = last_viewed_at.replace(tzinfo=None) if hasattr(last_viewed_at, 'replace') else last_viewed_at
            
        if not last_viewed_at or (db_updated_at and db_updated_at > last_viewed_at):
            has_new_shift = True

    return render_template(
        "calendar.html", 
        sent_dates=sent_dates or [],
        has_new_shift=has_new_shift,
        store_id=store_id,
        user_name=session.get("user_name"),
        target_month=target_month,
        shifts_js=shifts_for_js  # これをテンプレートの flaskData に渡す
    )
# どのファイルにあるか確認してください（おそらく calendar_page.py）
# calendar_page.py (または makeshift.py)

@calendar_bp.route("/admin") 
def admin(): 
    if "user_id" not in session: 
        return redirect(url_for("login.login")) 
    
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 店舗ID取得
        cursor.execute("SELECT store_id FROM account WHERE ID = %s", (user_id,))
        user_data = cursor.fetchone()
        store_id = user_data["store_id"] if user_data else None

        # ------------------------------------------------
        # 2. 「来月」の計算 (YYYY-MM形式にする)
        # ------------------------------------------------
        from datetime import datetime
        today = datetime.now()
        
        # 来月を計算
        if today.month == 12:
            next_month_dt = today.replace(year=today.year+1, month=1, day=1)
        else:
            next_month_dt = today.replace(month=today.month+1, day=1)
            
        # ★ここが重要: "2" ではなく "2026-02" という文字列を作る
        next_month_str = next_month_dt.strftime("%Y-%m") 

        # ------------------------------------------------
        # 3. その他の情報取得 (変更なし)
        # ------------------------------------------------
        cursor.execute("SELECT deadline_day FROM shift_settings WHERE store_id = %s", (store_id,))
        setting = cursor.fetchone()
        deadline_day = setting['deadline_day'] if setting and setting['deadline_day'] else 20
        
        is_application_open = (today.day <= deadline_day)

        cursor.execute("""
            SELECT is_published FROM shift_publish_status 
            WHERE store_id = %s AND target_month = %s
        """, (store_id, next_month_str))
        pub_status = cursor.fetchone()
        is_published = pub_status['is_published'] if pub_status else False

        # HTMLに渡す
        return render_template("admin.html", # ファイル名に合わせてください
                               next_month=next_month_str, # これで "2026-02" が渡る
                               deadline_day=deadline_day,
                               is_application_open=is_application_open,
                               is_published=is_published,
                               results=[])

    except Exception as e:
        print(f"Admin Error: {e}")
        return redirect(url_for("login.manager_home"))
    finally:
        if conn: conn.close()
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
        # 2. 自動切り替えロジック (期限を過ぎたらターゲットを翌々月にスライド)
        # ---------------------------------------------------
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        # 設定から締め切り日を取得
        cursor.execute("SELECT deadline_day FROM shift_settings WHERE store_id = %s", (store_id,))
        setting = cursor.fetchone()
        deadline_day = setting['deadline_day'] if setting and setting['deadline_day'] else 20

        today = datetime.now()
        target_date_obj = datetime.strptime(date, "%Y-%m-%d")

        # 🔹 A. 今月の締め切り日を算出 (例: 1月15日 23:59)
        this_month_deadline = today.replace(day=deadline_day, hour=23, minute=59, second=59)

        # 🔹 B. 今日の時点で「今月の期限」を過ぎているか判定
        if today > this_month_deadline:
            # 期限を過ぎたので、募集対象は「翌々月」にバトンタッチ
            # (1月16日なら、ターゲットは3月)
            recruiting_month = today + relativedelta(months=2)
        else:
            # 期限内なので、募集対象は「翌月」
            # (1月14日なら、ターゲットは2月)
            recruiting_month = today + relativedelta(months=1)

        # 🔹 C. ユーザーが開いた画面が「募集中の月」と一致するか判定
        is_locked = True
        if target_date_obj.year == recruiting_month.year and target_date_obj.month == recruiting_month.month:
            is_locked = False
        # 過去の月、当月、および翌々月以降は、is_locked = True のままなので編集できません

        # ---------------------------------------------------
        # 3. 既存のデータ・設定の取得 (表示用)
        # ---------------------------------------------------
        # 既存シフト希望データの取得
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

        # 時間フォーマット整形のヘルパー関数
        def format_time_str(t_obj):
            if t_obj is None: return None
            s = str(t_obj).strip()
            if ':' in s:
                parts = s.split(':')
                h = parts[0].zfill(2)
                m = parts[1]
                return f"{h}:{m}"
            return s[:5]

        # 店舗設定時間の取得
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
            # 提出期限を過ぎているかチェック
            if is_locked:
                flash(f"⛔ {deadline_day}日の提出期限を過ぎているため、変更できません。", "danger")
                return redirect(url_for("calendar.calendar"))

            work = request.form.get("work")
            start_time = request.form.get("start_time")
            end_time = request.form.get("end_time")

            # バリデーション (出勤希望の場合のみ)
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

            # データベース保存処理
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
                            is_locked=is_locked, 
                            deadline_day=deadline_day,
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
    
    # タイムゾーンなしの現在時刻を保存
    from datetime import datetime
    session["last_viewed_at"] = datetime.now()
    
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

    # 翌月の計算
    next_month_year = today.year if today.month < 12 else today.year + 1
    next_month = today.month + 1 if today.month < 12 else 1

    # 翌月かつ20日以内かチェック
    is_valid_period = (target_date_obj.year == next_month_year and 
                       target_date_obj.month == next_month and 
                       today.day <= deadline_day)

    if not is_valid_period:
        return jsonify({
            "status": "error", 
            "message": f"現在は{next_month}月分のシフト申請期間（20日まで）外です。"
        }), 403
    
    return jsonify({"status": "success", "message": "保存可能です"})