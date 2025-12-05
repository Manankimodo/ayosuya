from flask import Blueprint, render_template, redirect, url_for, session, request, flash
from sqlalchemy import text
from extensions import db  # ← extensionsからimport
import mysql.connector

calendar_bp = Blueprint("calendar", __name__, url_prefix="/calendar")

# DB接続
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="ayosuya"
    )

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
# 🔹 希望申請フォーム
# ==========================
@calendar_bp.route("/sinsei/<date>", methods=["GET", "POST"])
def sinsei(date):
    # 1. ログイン確認
    if "user_id" not in session:
        return redirect(url_for("login.login"))

    # ======================================================
    # ★設定と特別時間の取得
    # ======================================================
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 基本設定を取得
    cursor.execute("SELECT start_time, end_time, min_hours_per_day FROM shift_settings LIMIT 1")
    settings_row = cursor.fetchone()
    
    if settings_row:
        min_hours = float(settings_row['min_hours_per_day']) if settings_row['min_hours_per_day'] is not None else 0
        default_start = str(settings_row['start_time'])[:5] if settings_row['start_time'] else "09:00"
        default_end = str(settings_row['end_time'])[:5] if settings_row['end_time'] else "22:00"
    else:
        min_hours = 0
        default_start = "09:00"
        default_end = "22:00"
    
    # 特別時間があるか確認
    cursor.execute("SELECT start_time, end_time, reason FROM special_hours WHERE date = %s", (date,))
    special = cursor.fetchone()
    
    if special:
        # 特別時間を優先
        start_limit = str(special['start_time'])[:5]
        end_limit = str(special['end_time'])[:5]
        notice = f"⚠️ {special.get('reason', 'この日')}のため、営業時間が変更されています"
    else:
        # 基本設定を使用
        start_limit = default_start
        end_limit = default_end
        notice = None
    
    cursor.close()
    conn.close()

    # ======================================================
    # 2. 保存処理 (POST)
    # ======================================================
    if request.method == "POST":
        user_id = session["user_id"]
        name = request.form.get("name")
        work = request.form.get("work")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")

        # ★★★ バリデーション: 最低勤務時間チェック ★★★
        if work == "1" and start_time and end_time and min_hours > 0:
            from datetime import datetime
            start_dt = datetime.strptime(start_time, "%H:%M")
            end_dt = datetime.strptime(end_time, "%H:%M")
            diff = (end_dt - start_dt).total_seconds() / 3600
            
            if diff < 0:  # 日付またぎ
                diff += 24
            
            if diff < min_hours:
                flash(f"❌ 希望時間が短すぎます。最低 {min_hours} 時間以上入力してください（現在: {diff} 時間）", "danger")
                return render_template("sinsei.html", 
                                     date=date, 
                                     start_limit=start_limit,
                                     end_limit=end_limit,
                                     min_hours=min_hours,
                                     notice=notice)

        # 出勤不可なら時間はNone
        if work == "0":
            start_time = None
            end_time = None
        else:
            if start_time and not start_time.endswith(":00"):
                start_time += ":00"
            if end_time and not end_time.endswith(":00"):
                end_time += ":00"

        # すでに同じ日付の申請があるか確認
        check_sql = text("SELECT COUNT(*) FROM calendar WHERE ID = :user_id AND date = :date")
        result = db.session.execute(check_sql, {"user_id": user_id, "date": date}).scalar()

        if result > 0:
            # 更新
            update_sql = text("""
                UPDATE calendar
                SET work = :work, start_time = :start_time, end_time = :end_time
                WHERE ID = :user_id AND date = :date
            """)
            db.session.execute(update_sql, {
                "user_id": user_id,
                "date": date,
                "work": work,
                "start_time": start_time,
                "end_time": end_time
            })
            flash(f"{date} の希望を更新しました。", "info")
        else:
            # 新規登録
            insert_sql = text("""
                INSERT INTO calendar (ID, date, work, start_time, end_time)
                VALUES (:user_id, :date, :work, :start_time, :end_time)
            """)
            db.session.execute(insert_sql, {
                "user_id": user_id,
                "date": date,
                "work": work,
                "start_time": start_time,
                "end_time": end_time
            })
            flash(f"{date} の希望を提出しました。", "success")

        db.session.commit()
        return redirect(url_for("calendar.calendar"))

    # ======================================================
    # GET: フォーム表示
    # ======================================================
    return render_template("sinsei.html", 
                         date=date, 
                         start_limit=start_limit,
                         end_limit=end_limit,
                         min_hours=min_hours,
                         notice=notice)
# ==========================
# 🔹 確定シフト確認へのリダイレクト
# ==========================
@calendar_bp.route("/my_confirmed_shift")
def my_confirmed_shift():
    """
    セッションからIDを取得し、makeshiftブループリントの確認画面へ遷移させる。
    """
    if "user_id" not in session:
        # ログインしていない場合はログインページへ
        return redirect(url_for("login.login"))
        
    user_id = session["user_id"]
    
    # makeshift_bpで定義したシフト確認ビューへリダイレクト
    # user_idを引数として渡します。
    return redirect(url_for("makeshift.show_user_shift_view", user_id=user_id))


# ==========================
# 🔹 店長のヘルプ希望申請
# ==========================
@calendar_bp.route("/manager_help_request")
def manager_help_request():
    """店長用: ヘルプ希望申請カレンダー表示"""
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

    # ======================================================
    # ★追加: 設定 (min_hours) を取得して変数に入れる
    # ======================================================
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT min_hours_per_day FROM shift_settings LIMIT 1")
    settings_row = cursor.fetchone()
    
    # データがない場合やNoneの場合の対策
    if settings_row and settings_row['min_hours_per_day'] is not None:
        min_hours = float(settings_row['min_hours_per_day'])
    else:
        min_hours = 0
        
    cursor.close()
    conn.close()

    # ======================================================
    # 保存処理 (POST)
    # ======================================================
    if request.method == "POST":
        user_id = session["user_id"]
        work = request.form.get("work")
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")

        # ヘルプ不可なら時間はNone
        if work == "0":
            start_time = None
            end_time = None
        else:
            if start_time and not start_time.endswith(":00"):
                start_time += ":00"
            if end_time and not end_time.endswith(":00"):
                end_time += ":00"

        # ✅ すでに同じ日付の申請があるか確認
        check_sql = text("SELECT COUNT(*) FROM calendar WHERE ID = :user_id AND date = :date")
        result = db.session.execute(check_sql, {"user_id": user_id, "date": date}).scalar()

        if result > 0:
            # ✅ 更新
            update_sql = text("""
                UPDATE calendar
                SET work = :work, start_time = :start_time, end_time = :end_time
                WHERE ID = :user_id AND date = :date
            """)
            db.session.execute(update_sql, {
                "user_id": user_id,
                "date": date,
                "work": work,
                "start_time": start_time,
                "end_time": end_time
            })
            flash(f"{date} のヘルプ希望を更新しました。", "info")
        else:
            # ✅ 新規登録
            insert_sql = text("""
                INSERT INTO calendar (ID, date, work, start_time, end_time)
                VALUES (:user_id, :date, :work, :start_time, :end_time)
            """)
            db.session.execute(insert_sql, {
                "user_id": user_id,
                "date": date,
                "work": work,
                "start_time": start_time,
                "end_time": end_time
            })
            flash(f"{date} のヘルプ希望を提出しました。", "success")

        db.session.commit()

        return redirect(url_for("calendar.manager_help_request"))

    # ======================================================
    # ★修正: ここで min_hours を HTML に渡す！
    # ======================================================
    # HTML側で {{ store_id }} や {{ user_name }} を使っているなら、それらもここで渡す必要がありますが、
    # 今回は最低時間に関する修正のみ行っています。
    return render_template("manager_help_sinsei.html", date=date, min_hours=min_hours)