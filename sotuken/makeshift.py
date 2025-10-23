from flask import Blueprint
from ortools.sat.python import cp_model
import mysql.connector
from datetime import datetime, timedelta

makeshift_bp = Blueprint('makeshift', __name__, url_prefix='/makeshift')

# --- データベース接続 ---
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="ayosuya"
)
cursor = conn.cursor(dictionary=True)

# --- calendarテーブルからデータ取得 ---
cursor.execute("SELECT ID, date, start_time, end_time FROM calendar ORDER BY date, start_time")
rows = cursor.fetchall()


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


# --- 日付一覧を取得 ---
days = sorted(set(row["date"].strftime("%Y-%m-%d") for row in rows))

# --- 各日付ごとに登録済み時間を整理 ---
calendar_data = {}
for d in days:
    calendar_data[d] = []
    for r in rows:
        if r["date"].strftime("%Y-%m-%d") == d:
            calendar_data[d].append((format_time(r["start_time"]), format_time(r["end_time"])))


# --- 空き時間を探す関数 ---
def find_free_times(registered_times, interval_minutes=60):
    """
    registered_times: [(start, end), ...]
    interval_minutes: 区切り分数（例：60, 30, 15）
    """
    full_day_start = datetime.strptime("00:00", "%H:%M")
    full_day_end = full_day_start + timedelta(days=1)  # ✅ 翌日の00:00を「24:00」扱い

    # --- 登録済みを時間型に変換 ---
    registered = []
    for s, e in registered_times:
        s_time = datetime.strptime(s, "%H:%M")
        e_time = datetime.strptime(e, "%H:%M") if e != "00:00" else full_day_end
        registered.append((s_time, e_time))

    # --- 重複・交差をまとめる ---
    registered.sort()
    merged = []
    for start, end in registered:
        if not merged or merged[-1][1] < start:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    registered = merged

    # --- 空き時間を計算 ---
    free_slots = []
    current_time = full_day_start

    for start, end in registered:
        if current_time < start:
            free_slots.append((current_time.strftime("%H:%M"), start.strftime("%H:%M")))
        current_time = max(current_time, end)

    # --- 最後の申請後も空いている場合（例：18:22〜24:00） ---
    if current_time < full_day_end:
        free_slots.append((current_time.strftime("%H:%M"), "24:00"))

    # --- 空きを指定間隔で分割 ---
    divided_slots = []
    for s, e in free_slots:
        st = datetime.strptime(s, "%H:%M")
        en = full_day_end if e == "24:00" else datetime.strptime(e, "%H:%M")
        while st < en:
            next_t = min(st + timedelta(minutes=interval_minutes), en)
            divided_slots.append((st.strftime("%H:%M"), next_t.strftime("%H:%M")))
            st = next_t

    return divided_slots


# --- 結果表示 ---
print("\n=== 空き時間表示（24:00対応版） ===")
for d in days:
    print(f"\n【{d}】")

    registered = calendar_data[d]
    if not registered:
        print(" 終日空き")
        continue

    # 登録済み時間を表示
    for s, e in registered:
        print(f" 申請あり：{s}〜{e}")

    # 空き時間を算出（15分単位や30分単位もOK）
    free_slots = find_free_times(registered, interval_minutes=60)

    for s, e in free_slots:
        print(f" 空き：{s}〜{e}")

cursor.close()
conn.close()
