from flask import Blueprint, render_template, jsonify, request, redirect, url_for
import mysql.connector
from datetime import datetime, timedelta

makeshift_bp = Blueprint('makeshift', __name__, url_prefix='/makeshift')


# === DB接続 ===
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="ayosuya"
    )


# === 時刻フォーマット変換 ===
def format_time(value):
    """MySQL TIME型 (timedelta or str) → HH:MM形式に変換"""
    if not value:
        return None
    if isinstance(value, str):
        return value[:5]
    elif hasattr(value, "seconds"):
        total_seconds = value.seconds
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"
    return None


# === 空き時間を計算 ===
def find_free_times(registered_times):
    """1日の中の空き時間を返す（出勤がない時間帯を全て出す）"""
    full_day_start = datetime.strptime("00:00", "%H:%M")
    full_day_end = datetime.strptime("23:59", "%H:%M")

    # 登録なしなら全日空き
    if not registered_times:
        return [(full_day_start.strftime("%H:%M"), full_day_end.strftime("%H:%M"))]

    # 文字列→datetimeに変換
    intervals = []
    for s, e in registered_times:
        try:
            start = datetime.strptime(s, "%H:%M")
            end = datetime.strptime(e, "%H:%M")
            if start < end:
                intervals.append((start, end))
        except Exception:
            continue

    # 時間帯をマージ
    intervals.sort()
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    # 空き時間を抽出
    free_slots = []
    current = full_day_start
    for start, end in merged:
        if current < start:
            free_slots.append((current.strftime("%H:%M"), start.strftime("%H:%M")))
        current = max(current, end)
    if current < full_day_end:
        free_slots.append((current.strftime("%H:%M"), "23:59"))

    return free_slots


# === 管理者画面 ===
@makeshift_bp.route("/admin")
def show_admin_shift():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT ID, date, start_time, end_time FROM calendar ORDER BY date, start_time")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return render_template("admin.html", results=[])

    days = sorted(set(r["date"].strftime("%Y-%m-%d") for r in rows))
    results = []
    for d in days:
        registered = [
            (format_time(r["start_time"]), format_time(r["end_time"]))
            for r in rows
            if r["date"].strftime("%Y-%m-%d") == d and r["start_time"] and r["end_time"]
        ]
        free_slots = find_free_times(registered)
        results.append({"date": d, "registered": registered, "free_slots": free_slots})

    return render_template("admin.html", results=results)


@makeshift_bp.route("/day/<date_str>")
def get_day_details(date_str):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT ID, date, start_time, end_time 
        FROM calendar 
        WHERE date = %s 
        ORDER BY start_time
    """, (date_str,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return jsonify({
            "date": date_str,
            "users": {},
            "free_slots": [["00:00", "23:59"]]
        })

    user_dict = {}
    for r in rows:
        uid = r["ID"]
        if uid not in user_dict:
            user_dict[uid] = []

        if r["start_time"] and r["end_time"]:
            user_dict[uid].append([
                format_time(r["start_time"]),
                format_time(r["end_time"])
            ])
        else:
            user_dict[uid].append(["出勤できない", ""])

    # 全ユーザーの登録時間（出勤できないを除外）
    all_registered = [
        slot for slots in user_dict.values() for slot in slots if slot[0] != "出勤できない"
    ]
    # free_slotsもリスト形式に統一
    free_slots = [list(fs) for fs in find_free_times(all_registered)]

    return jsonify({
        "date": date_str,
        "users": user_dict,
        "free_slots": free_slots
    })


# === シフト遷移 ===
@makeshift_bp.route("/generate")
def generate_shift():
    print("🧮 シフト自動作成画面に遷移しました！")
    return redirect(url_for('makeshift.show_admin_shift'))
#------------------------------------------------------------------------------------------

@makeshift_bp.route("/auto_calendar")
def auto_calendar():
    """
    設定を反映してシフト自動作成を実行し、結果をカレンダー画面で表示
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # --- ✅ 最新の設定を取得 ---
    cursor.execute("SELECT * FROM shift_settings ORDER BY updated_at DESC LIMIT 1")
    settings = cursor.fetchone()

    # デフォルト設定（未設定時）
    if not settings:
        settings = {
            "start_time": "09:00:00",
            "end_time": "18:00:00",
            "break_minutes": 60,
            "interval_minutes": 60,
            "max_hours_per_day": 8,
            "min_hours_per_day": 4,
            "max_people_per_shift": 2,
            "auto_mode": "balance"
        }

    # --- 希望データを取得 ---
    cursor.execute("""
        SELECT ID AS user_id, date, start_time, end_time
        FROM calendar
        ORDER BY date, start_time
    """)
    rows = cursor.fetchall()

    if not rows:
        cursor.close()
        conn.close()
        return render_template("auto_calendar.html", shifts=[], message="希望データがありません。")

    # --- shift_table を初期化 ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shift_table (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(255),
            date DATE,
            start_time TIME,
            end_time TIME
        )
    """)
    cursor.execute("DELETE FROM shift_table")

    from ortools.sat.python import cp_model
    from datetime import datetime, timedelta
    import random

    days = sorted(set(r["date"] for r in rows))
    result_all = []

    # --- 各日ごとのシフト作成 ---
    for day in days:
        day_requests = [r for r in rows if r["date"] == day]
        users = list(set(r["user_id"] for r in day_requests))

        model = cp_model.CpModel()
        x = {u: model.NewBoolVar(f"x_{u}") for u in users}

        # ✅ 各日ごとの人数制限（設定反映）
        needed = min(len(users), settings["max_people_per_shift"])
        model.Add(sum(x[u] for u in users) == needed)

        # --- モード別処理 ---
        if settings["auto_mode"] == "random":
            for u in users:
                if random.random() > 0.5:
                    model.Add(x[u] == 1)

        solver = cp_model.CpSolver()
        solver.Solve(model)


        # MySQL TIME型はtimedeltaとして返ることがあるため文字列に変換
        def to_time_str(value):
            if isinstance(value, timedelta):
                total_seconds = int(value.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                return f"{hours:02d}:{minutes:02d}:00"
            elif isinstance(value, str):
                return value
            else:
                return "00:00:00"

        shift_start_str = to_time_str(settings["start_time"])
        shift_end_str = to_time_str(settings["end_time"])

        shift_start = datetime.strptime(shift_start_str, "%H:%M:%S")
        shift_end = datetime.strptime(shift_end_str, "%H:%M:%S")
        interval = timedelta(minutes=settings["interval_minutes"])
        break_time = timedelta(minutes=settings["break_minutes"])


        current_start = shift_start

        while current_start + interval <= shift_end:
            current_end = current_start + interval
            for u in users:
                if solver.Value(x[u]) == 1:
                    cursor.execute("""
                        INSERT INTO shift_table (user_id, date, start_time, end_time)
                        VALUES (%s, %s, %s, %s)
                    """, (u, day, current_start.time(), current_end.time()))

                    result_all.append({
                        "date": day.strftime("%Y-%m-%d"),
                        "user_id": u,
                        "start_time": current_start.strftime("%H:%M"),
                        "end_time": current_end.strftime("%H:%M")
                    })
            # 休憩を考慮して次の時間帯へ
            current_start = current_end + break_time

    conn.commit()
    cursor.close()
    conn.close()

    return render_template(
        "auto_calendar.html",
        shifts=result_all,
        message="✅ 設定を反映して自動作成が完了しました！",
        settings=settings
    )

#-----------------------------------------------------------------------------------------------------
# === 管理者シフト設定画面 ===
@makeshift_bp.route("/setting", methods=["GET", "POST"])
def shift_setting():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        try:
            # 現在のレコード件数を確認
            cursor.execute("SELECT COUNT(*) AS cnt FROM shift_settings")
            count = cursor.fetchone()["cnt"]

            # 値を取得
            data = (
                request.form["start_time"],
                request.form["end_time"],
                request.form["break_minutes"],
                request.form["interval_minutes"],
                request.form["max_hours_per_day"],
                request.form["min_hours_per_day"],
                request.form["max_people_per_shift"],
                request.form["auto_mode"]
            )

            # 新規 or 更新
            if count == 0:
                cursor.execute("""
                    INSERT INTO shift_settings (
                        start_time, end_time, break_minutes, interval_minutes,
                        max_hours_per_day, min_hours_per_day, max_people_per_shift, auto_mode
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """, data)
            else:
                cursor.execute("""
                    UPDATE shift_settings
                    SET start_time=%s, end_time=%s, break_minutes=%s, interval_minutes=%s,
                        max_hours_per_day=%s, min_hours_per_day=%s,
                        max_people_per_shift=%s, auto_mode=%s
                """, data)

            conn.commit()

        except Exception as e:
            conn.rollback()
            raise e

    # 最新設定を取得して表示
    cursor.execute("SELECT * FROM shift_settings LIMIT 1")
    setting = cursor.fetchone()
    conn.close()

    if not setting:
        setting = {
            "start_time": "09:00",
            "end_time": "18:00",
            "break_minutes": 60,
            "interval_minutes": 60,
            "max_hours_per_day": 8,
            "min_hours_per_day": 4,
            "max_people_per_shift": 3,
            "auto_mode": "balance"
        }

    return render_template("shift_setting.html", settings=setting)
#------------------------------------------------------------------------------------------------------------
def get_shift_settings():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM shift_settings ORDER BY updated_at DESC LIMIT 1")
    settings = cursor.fetchone()
    cursor.close()
    conn.close()
    return settings

def generate_auto_shifts(settings):
    """設定を反映した自動シフト生成"""
    start_time = datetime.strptime(settings["start_time"], "%H:%M")
    end_time = datetime.strptime(settings["end_time"], "%H:%M")
    interval = timedelta(minutes=settings["interval_minutes"])
    break_minutes = settings["break_minutes"]
    max_hours = settings["max_hours_per_day"]
    min_hours = settings["min_hours_per_day"]
    mode = settings["auto_mode"]

    shifts = []

    current_time = start_time
    while current_time < end_time:
        next_time = current_time + interval
        shifts.append({
            "start": current_time.strftime("%H:%M"),
            "end": next_time.strftime("%H:%M"),
            "max_people": settings["max_people_per_shift"],
        })
        current_time = next_time

    # mode に応じたロジックを追加（例）
    if mode == "balance":
        # 全員のシフト時間を均等にする処理
        pass
    elif mode == "preference":
        # 希望を優先した割り当て処理
        pass
    elif mode == "random":
        # ランダム割り当て処理
        pass

    return shifts

