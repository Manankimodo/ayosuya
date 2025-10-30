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
    シフト自動作成を実行し、結果をカレンダー画面で表示
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # --- 全希望データを取得 ---
    cursor.execute("""
        SELECT ID as user_id, date, start_time, end_time
        FROM calendar
        ORDER BY date, start_time
    """)
    rows = cursor.fetchall()

    if not rows:
        cursor.close()
        conn.close()
        return render_template("auto_calendar.html", shifts=[], message="希望データがありません。")

    # --- shift_table を作成（なければ） ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shift_table (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(255),
            date DATE,
            start_time TIME,
            end_time TIME
        )
    """)

    # --- 既存シフトを全削除して再生成 ---
    cursor.execute("DELETE FROM shift_table")

    # --- 日付ごとにOR-Toolsでシフト作成 ---
    from ortools.sat.python import cp_model
    days = sorted(set(r["date"] for r in rows))
    result_all = []

    for day in days:
        day_requests = [r for r in rows if r["date"] == day]
        users = list(set([r["user_id"] for r in day_requests]))

        model = cp_model.CpModel()
        x = {u: model.NewBoolVar(f"x_{u}") for u in users}

        # 必要人数（仮に2人）
        needed = min(len(users), 2)
        model.Add(sum(x[u] for u in users) == needed)

        solver = cp_model.CpSolver()
        solver.Solve(model)

        # 保存
        for u in users:
            if solver.Value(x[u]) == 1:
                target = next((r for r in day_requests if r["user_id"] == u), None)
                start_time = target["start_time"] if target else None
                end_time = target["end_time"] if target else None
                cursor.execute("""
                    INSERT INTO shift_table (user_id, date, start_time, end_time)
                    VALUES (%s, %s, %s, %s)
                """, (u, day, start_time, end_time))
                result_all.append({
                    "date": day.strftime("%Y-%m-%d"),
                    "user_id": u,
                    "start_time": format_time(start_time),
                    "end_time": format_time(end_time)
                })

    conn.commit()
    cursor.close()
    conn.close()

    return render_template("auto_calendar.html", shifts=result_all, message="自動作成が完了しました！")





