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
    希望データをできる限り反映し、6時間以上勤務なら休憩を自動挿入
    """
    from ortools.sat.python import cp_model
    from datetime import datetime, timedelta, time as time_cls
    import random

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # --- ✅ 設定取得 ---
    cursor.execute("SELECT * FROM shift_settings ORDER BY updated_at DESC LIMIT 1")
    settings = cursor.fetchone()
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

    # --- ✅ 希望シフト取得 ---
    cursor.execute("""
        SELECT user_id AS user_id, date, start_time, end_time
        FROM calendar
        ORDER BY date, start_time
    """)
    rows = cursor.fetchall()
    if not rows:
        cursor.close()
        conn.close()
        return render_template("auto_calendar.html", shifts=[], message="希望データがありません。")

    # --- ✅ shift_table 初期化 ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shift_table (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(255),
            date DATE,
            start_time TIME,
            end_time TIME,
            type VARCHAR(50) DEFAULT 'work'
        )
    """)
    cursor.execute("DELETE FROM shift_table")

    # --- 共通関数 ---
    def ensure_time_obj(v):
        """datetime, timedelta, str すべて安全に time 型へ変換"""
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
        # フォールバック
        return datetime.strptime("00:00:00", "%H:%M:%S").time()

    def to_time_str(v):
        if isinstance(v, timedelta):
            total_seconds = int(v.total_seconds())
            h = total_seconds // 3600
            m = (total_seconds % 3600) // 60
            return f"{h:02d}:{m:02d}:00"
        elif isinstance(v, str):
            return v
        else:
            return "00:00:00"

    def to_time_obj(v):
        return ensure_time_obj(v)

    # --- OR-Toolsで日ごとに最適化 ---
    days = sorted(set(r["date"] for r in rows))
    result_all = []
    
    for day in days:
        day_requests = [r for r in rows if r["date"] == day]
        users = list(set(r["user_id"] for r in day_requests))

        shift_start = datetime.strptime(to_time_str(settings["start_time"]), "%H:%M:%S")
        shift_end = datetime.strptime(to_time_str(settings["end_time"]), "%H:%M:%S")
        interval = timedelta(minutes=settings["interval_minutes"])

        # --- シフト時間帯作成 ---
        timeslots = []
        current = shift_start
        while current + interval <= shift_end:
            timeslots.append((current, current + interval))
            current += interval

        model = cp_model.CpModel()
        x = {(u, t): model.NewBoolVar(f"x_{u}_{t}") for u in users for t in range(len(timeslots))}

        # --- 人数制限 ---
        for t in range(len(timeslots)):
            model.Add(sum(x[(u, t)] for u in users) <= settings["max_people_per_shift"])

        # --- 希望を優先的に反映 ---
        for r in day_requests:
            try:
                req_start = datetime.strptime(str(r["start_time"]), "%H:%M:%S")
                req_end = datetime.strptime(str(r["end_time"]), "%H:%M:%S")
            except:
                continue

            for t, (s, e) in enumerate(timeslots):
                if s >= req_start and e <= req_end:
                    model.AddHint(x[(r["user_id"], t)], 1)
                else:
                    model.AddHint(x[(r["user_id"], t)], 0)

        # --- 公平モード（balance） ---
        if settings["auto_mode"] == "balance":
            total_work = {u: sum(x[(u, t)] for t in range(len(timeslots))) for u in users}
            model.Minimize(sum(abs(total_work[u1] - total_work[u2]) for u1 in users for u2 in users))

        # --- ランダムモード ---
        elif settings["auto_mode"] == "random":
            for u in users:
                for t in range(len(timeslots)):
                    if random.random() < 0.5:
                        model.Add(x[(u, t)] == 1)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 10
        solver.Solve(model)

        # --- 結果登録 ---
        for t, (s, e) in enumerate(timeslots):
            assigned_users = [u for u in users if solver.Value(x[(u, t)]) == 1]
            for u in assigned_users:
                cursor.execute("""
                    INSERT INTO shift_table (user_id, date, start_time, end_time, type)
                    VALUES (%s, %s, %s, %s, 'work')
                """, (u, day, to_time_obj(s), to_time_obj(e)))
                result_all.append({
                    "date": str(day),
                    "user_id": u,
                    "start_time": s.strftime("%H:%M"),
                    "end_time": e.strftime("%H:%M"),
                    "type": "work"
                })

    # --- ✅ 6時間以上勤務なら休憩を追加 ---
    cursor.execute("""
        SELECT user_id, date, MIN(start_time) AS start_time, MAX(end_time) AS end_time
        FROM shift_table
        WHERE type = 'work'
        GROUP BY user_id, date
    """)
    work_blocks = cursor.fetchall()

    for block in work_blocks:
        start_time = ensure_time_obj(block["start_time"])
        end_time = ensure_time_obj(block["end_time"])
        start = datetime.combine(block["date"], start_time)
        end = datetime.combine(block["date"], end_time)

        total_hours = (end - start).total_seconds() / 3600
        if total_hours >= 6:
            break_start = start + timedelta(hours=3)
            break_end = break_start + timedelta(minutes=settings["break_minutes"])

            cursor.execute("""
                INSERT INTO shift_table (user_id, date, start_time, end_time, type)
                VALUES (%s, %s, %s, %s, 'break')
            """, (block["user_id"], block["date"], break_start.time(), break_end.time()))

            result_all.append({
                "date": str(block["date"]),
                "user_id": block["user_id"],
                "start_time": break_start.strftime("%H:%M"),
                "end_time": break_end.strftime("%H:%M"),
                "type": "break"
            })

    conn.commit()
    cursor.close()
    conn.close()

    return render_template(
        "auto_calendar.html",
        shifts=result_all,
        settings=settings,
        message="✅ 希望を考慮して自動シフトを作成しました！（6時間以上勤務には休憩を自動追加）"
    )


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

#------------------------------------------------------------------------------------------------------------

@makeshift_bp.route("/settings", methods=["GET", "POST"])
def settings():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # --- 現在の設定を取得 ---
    cursor.execute("SELECT * FROM shift_settings LIMIT 1")
    settings = cursor.fetchone()

    # --- データが存在しない場合の初期化 ---
    if not settings:
        settings = {
            "start_time": "09:00",
            "end_time": "18:00",
            "break_minutes": 60,
            "interval_minutes": 60,
            "max_hours_per_day": 8,
            "min_hours_per_day": 4,
            "max_people_per_shift": 3,
            "auto_mode": "balance",
            "updated_at": None,
        }

    # --- POST（更新処理） ---
    if request.method == "POST":
        start_time = request.form["start_time"]
        end_time = request.form["end_time"]
        break_minutes = request.form["break_minutes"]
        interval_minutes = request.form["interval_minutes"]
        max_hours_per_day = request.form["max_hours_per_day"]
        min_hours_per_day = request.form["min_hours_per_day"]
        max_people_per_shift = request.form["max_people_per_shift"]
        auto_mode = request.form["auto_mode"]

        cursor.execute("""
            UPDATE shift_settings
            SET start_time=%s, end_time=%s, break_minutes=%s, interval_minutes=%s,
                max_hours_per_day=%s, min_hours_per_day=%s, max_people_per_shift=%s,
                auto_mode=%s, updated_at=NOW()
        """, (
            start_time, end_time, break_minutes, interval_minutes,
            max_hours_per_day, min_hours_per_day, max_people_per_shift, auto_mode
        ))
        conn.commit()
        conn.close()
        return redirect(url_for("makeshift.settings"))  # 保存後に再表示

    conn.close()

    # --- 🕒 時刻を文字列フォーマットに変換（--:--対策） ---
    for key in ["start_time", "end_time"]:
        if settings[key]:
            # 例: datetime.time(9, 0, 0) → "09:00"
            settings[key] = str(settings[key])[:5]
        else:
            # デフォルト値を設定
            settings[key] = "09:00" if key == "start_time" else "18:00"

    return render_template("shift_setting.html", settings=settings)
