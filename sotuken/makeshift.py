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
    （ユーザー希望を考慮して OR-Tools で最適化）
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # --- 最新の設定を取得 ---
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
            "min_hours_per_day": 0,
            "max_people_per_shift": 2,
            "auto_mode": "balance"
        }

    # --- 希望データを取得（calendar テーブル） ---
    cursor.execute("""
        SELECT ID AS user_id, date, start_time, end_time
        FROM calendar
        ORDER BY date, start_time
    """)
    rows = cursor.fetchall()

    if not rows:
        cursor.close()
        conn.close()
        return render_template("auto_calendar.html", shifts=[], message="希望データがありません。", settings=settings)

    # --- shift_table（作業用）を初期化 ---
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

    # --- ヘルパー: MySQL TIME（timedelta など）を "HH:MM:SS" 文字列に変換 ---
    from datetime import datetime, timedelta, time
    def to_time_str(value):
        # MySQL TIME が timedelta として返ってくることがあるので対応
        if isinstance(value, timedelta):
            total_seconds = int(value.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        elif isinstance(value, time):
            return value.strftime("%H:%M:%S")
        elif isinstance(value, str):
            # すでに "HH:MM" や "HH:MM:SS" の場合
            # normalize to HH:MM:SS
            parts = value.split(':')
            if len(parts) == 2:
                return f"{parts[0]}:{parts[1]}:00"
            return value
        else:
            return "00:00:00"

    # --- 設定から時間を取得（datetime に変換） ---
    shift_start_str = to_time_str(settings["start_time"])
    shift_end_str = to_time_str(settings["end_time"])
    shift_start_time = datetime.strptime(shift_start_str, "%H:%M:%S")
    shift_end_time = datetime.strptime(shift_end_str, "%H:%M:%S")

    interval_minutes = int(settings["interval_minutes"])
    break_minutes = int(settings.get("break_minutes", 0))
    max_hours_per_day = float(settings.get("max_hours_per_day", 8))
    min_hours_per_day = float(settings.get("min_hours_per_day", 0))
    max_people_per_shift = int(settings.get("max_people_per_shift", 2))
    mode = settings.get("auto_mode", "balance")

    # --- 日付ごとにスロットを作るため、全日付を取得 ---
    days = sorted({r["date"] for r in rows})
    result_all = []

    # OR-Tools
    from ortools.sat.python import cp_model
    import random as pyrandom

    # --- 日ごとに最適化を実行 ---
    for day in days:
        # その日の全希望行
        day_requests = [r for r in rows if r["date"] == day]

        # --- ユーザーごとの希望スロットリストを作成 ---
        # 各希望行 r: start_time, end_time が可能範囲
        # normalize times to datetime on that day
        normalized_requests = []
        for r in day_requests:
            # start_time/end_time may be TIME (timedelta) or str
            s_str = to_time_str(r["start_time"])
            e_str = to_time_str(r["end_time"])
            s_dt = datetime.strptime(s_str, "%H:%M:%S")
            e_dt = datetime.strptime(e_str, "%H:%M:%S")
            normalized_requests.append({
                "user_id": r["user_id"],
                "start_dt": s_dt,
                "end_dt": e_dt
            })

        # --- 時間スロットを作る（設定の interval と break を反映） ---
        slots = []  # each slot is tuple (slot_start_dt, slot_end_dt)
        cur = shift_start_time
        interval_td = timedelta(minutes=interval_minutes)
        break_td = timedelta(minutes=break_minutes)

        while cur + interval_td <= shift_end_time:
            slot_start = cur
            slot_end = cur + interval_td
            slots.append((slot_start, slot_end))
            cur = slot_end + break_td

        num_slots = len(slots)
        if num_slots == 0:
            # その日はスロットが生成されない（設定が変）
            continue

        # --- 各スロットに出られるユーザーを判定 ---
        # possible[u][s] = True if user u is available for slot s
        users = sorted({r["user_id"] for r in normalized_requests})
        if not users:
            continue

        # preference score: how many request segments a user submitted that overlap any slot
        preference_count = {u: 0 for u in users}
        user_available_slots = {u: [] for u in users}
        for i, (slot_s, slot_e) in enumerate(slots):
            for req in normalized_requests:
                u = req["user_id"]
                # treat availability if request interval overlaps slot interval
                # overlap if req.start_dt < slot_end and req.end_dt > slot_start
                if (req["start_dt"] < slot_e) and (req["end_dt"] > slot_s):
                    user_available_slots[u].append(i)
                    preference_count[u] += 1

        # If a user has zero available slots, they cannot be assigned this day.
        # Also compute max slots allowed per user (based on max_hours_per_day)
        slot_length_hours = interval_td.total_seconds() / 3600.0
        max_slots_per_user = max(1, int(max_hours_per_day / slot_length_hours))

        model = cp_model.CpModel()

        # Boolean variable assign[(u,s)] if user u assigned to slot s
        assign = {}
        for u in users:
            for s in range(num_slots):
                # Only create variable if user is available for that slot
                if s in user_available_slots[u]:
                    assign[(u, s)] = model.NewBoolVar(f"assign_{u}_{s}")

        # Constraint: each slot has at most max_people_per_shift assigned
        for s in range(num_slots):
            vars_in_slot = [assign[(u, s)] for u in users if (u, s) in assign]
            if vars_in_slot:
                model.Add(sum(vars_in_slot) <= max_people_per_shift)

        # Constraint: per-user max slots (so max_hours_per_day honored)
        for u in users:
            vars_for_user = [assign[(u, s)] for s in range(num_slots) if (u, s) in assign]
            if vars_for_user:
                model.Add(sum(vars_for_user) <= max_slots_per_user)

        # Optional: ensure a user is not assigned overlapping slots (slots are non-overlapping by construction)
        # If you want to limit that a user can be assigned at most 1 contiguous block, more complex constraints are needed.

        # Build objective based on mode
        solver = cp_model.CpSolver()
        # preference mode: maximize sum(assign * preference_count[u]) to favor users who requested more
        if mode == "preference":
            objective_terms = []
            for (u, s), var in assign.items():
                weight = preference_count.get(u, 1)
                objective_terms.append(var * weight)
            model.Maximize(sum(objective_terms))

        elif mode == "random":
            # maximize random tiny weights to break ties randomly
            objective_terms = []
            for (u, s), var in assign.items():
                w = pyrandom.random()  # float in [0,1)
                # cp_model requires integers: scale up
                weight = int(w * 100)
                objective_terms.append(var * weight)
            model.Maximize(sum(objective_terms))

        else:  # "balance" (default)
            # minimize the maximum number of slots assigned to any user (to reduce skew)
            # create int var max_assigned and constrain sum(vars_for_user) <= max_assigned
            max_assigned = model.NewIntVar(0, num_slots, "max_assigned")
            for u in users:
                vars_for_user = [assign[(u, s)] for s in range(num_slots) if (u, s) in assign]
                if vars_for_user:
                    model.Add(sum(vars_for_user) <= max_assigned)
            model.Minimize(max_assigned)

        # Solve with a reasonable time limit
        solver.parameters.max_time_in_seconds = 5.0
        solver.parameters.num_search_workers = 8
        res = solver.Solve(model)

        # Collect assigned results for this day
        # For each slot, list assigned users and insert into shift_table
        for s_idx, (slot_s, slot_e) in enumerate(slots):
            assigned_users = []
            for u in users:
                key = (u, s_idx)
                if key in assign and solver.Value(assign[key]) == 1:
                    assigned_users.append(u)

            # insert assigned users for this slot
            for u in assigned_users:
                cursor.execute("""
                    INSERT INTO shift_table (user_id, date, start_time, end_time)
                    VALUES (%s, %s, %s, %s)
                """, (u, day, slot_s.time(), slot_e.time()))

                result_all.append({
                    "date": day.strftime("%Y-%m-%d"),
                    "user_id": u,
                    "start_time": slot_s.strftime("%H:%M"),
                    "end_time": slot_e.strftime("%H:%M")
                })

    # commit once per run
    conn.commit()
    cursor.close()
    conn.close()

    return render_template(
        "auto_calendar.html",
        shifts=result_all,
        message="✅ 設定と希望を反映して自動作成が完了しました！",
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

