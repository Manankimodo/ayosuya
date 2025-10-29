from flask import Blueprint, render_template, jsonify, request, redirect, url_for
import mysql.connector
from datetime import datetime, timedelta

makeshift_bp = Blueprint('makeshift', __name__, url_prefix='/makeshift')

# --- データベース接続 ---
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="ayosuya"
    )


def format_time(value):
    """MySQL TIME型 (timedelta) を HH:MM 形式に変換"""
    if isinstance(value, str):
        return value[:5]
    elif hasattr(value, "seconds"):
        total_seconds = value.seconds
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"
    return "??:??"


def find_free_times(registered_times, interval_minutes=60):
    """1日の中の空き時間を返す"""
    full_day_start = datetime.strptime("00:00", "%H:%M")
    full_day_end = full_day_start + timedelta(days=1)  # 24:00扱い

    # --- 登録済み時間を datetime 型に変換 ---
    registered = []
    for s, e in registered_times:
        s_time = datetime.strptime(s, "%H:%M")
        e_time = datetime.strptime(e, "%H:%M") if e != "00:00" else full_day_end
        registered.append((s_time, e_time))

    # --- 重複をマージ ---
    registered.sort()
    merged = []
    for start, end in registered:
        if not merged or merged[-1][1] < start:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    registered = merged

    # --- 空き時間を探す ---
    free_slots = []
    current_time = full_day_start

    for start, end in registered:
        if current_time < start:
            free_slots.append((current_time.strftime("%H:%M"), start.strftime("%H:%M")))
        current_time = max(current_time, end)

    # --- 最後の申請後も空きがあれば追加（〜24:00）---
    if current_time < full_day_end:
        free_slots.append((current_time.strftime("%H:%M"), "24:00"))

    # --- 空きを指定時間で分割 ---
    divided_slots = []
    for s, e in free_slots:
        st = datetime.strptime(s, "%H:%M")
        en = full_day_end if e == "24:00" else datetime.strptime(e, "%H:%M")
        while st < en:
            next_t = min(st + timedelta(minutes=interval_minutes), en)
            divided_slots.append((st.strftime("%H:%M"), next_t.strftime("%H:%M")))
            st = next_t
    return divided_slots


# ---------------------------------------------------------------------
# 管理者画面（希望時間と空き時間の一覧）
# ---------------------------------------------------------------------
@makeshift_bp.route("/admin")
def show_admin_shift():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT ID, date, start_time, end_time FROM calendar ORDER BY date, start_time")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        print("⚠️ rows が空です")
        return render_template("admin.html", results=[])

    days = sorted(set(r["date"].strftime("%Y-%m-%d") for r in rows))
    results = []
    for d in days:
        registered = [
            (format_time(r["start_time"]), format_time(r["end_time"]))
            for r in rows if r["date"].strftime("%Y-%m-%d") == d
        ]
        free_slots = find_free_times(registered, interval_minutes=60)
        results.append({
            "date": d,
            "registered": registered,
            "free_slots": free_slots
        })

    print("✅ results生成完了 件数:", len(results))
    return render_template("admin.html", results=results)


# ---------------------------------------------------------------------
# シフト自動作成API
# ---------------------------------------------------------------------
@makeshift_bp.route("/generate", methods=["GET", "POST"])
def generate_shift():
    if request.method == "POST":
        print("🧮 シフトを自動作成しました！")
        return jsonify({"status": "ok", "redirect": url_for('makeshift.show_admin_shift')})
    else:
        # GETは /admin に直接リダイレクト
        return redirect(url_for('makeshift.show_admin_shift'))


# ---------------------------------------------------------------------
# イベント表示用API（今はコメントアウトでOK）
# ---------------------------------------------------------------------
# @makeshift_bp.route("/events")
# def get_events():
#     conn = get_db_connection()
#     cursor = conn.cursor(dictionary=True)
#     cursor.execute("""
#         SELECT date, start_time, end_time, ID
#         FROM calendar
#         ORDER BY date, start_time
#     """)
#     rows = cursor.fetchall()
#     cursor.close()
#     conn.close()

#     events = []
#     for r in rows:
#         events.append({
#             "title": f"ID: {r['ID']}",
#             "start": f"{r['date']}T{r['start_time']}",
#             "end": f"{r['date']}T{r['end_time']}"
#         })
#     return jsonify(events)
