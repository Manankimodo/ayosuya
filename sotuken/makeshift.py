from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from ortools.sat.python import cp_model
from extensions import db  # ✅ extensions から import
import mysql.connector
from ortools.sat.python import cp_model

# --- データベース接続 ---
conn = mysql.connector.connect(
    host="localhost",
    user="root",          # ←あなたの設定に合わせて変更
    password="", # ←あなたの設定に合わせて変更
    database="ayosuya"    # ←あなたのDB名に合わせて変更
)
cursor = conn.cursor(dictionary=True)

# --- calendarテーブルからデータ取得 ---
cursor.execute("SELECT ID, date, start_time, end_time FROM calendar ORDER BY date, start_time")
rows = cursor.fetchall()

# --- timedelta対応関数 ---
def format_time(value):
    """MySQL TIME型 (timedelta) を HH:MM 形式の文字列に変換"""
    if isinstance(value, str):  # 文字列ならそのまま扱う
        return value[:5]
    elif hasattr(value, "seconds"):  # timedelta型なら手動で整形
        total_seconds = value.seconds
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"
    else:
        return "??:??"

# --- データ整形 ---
employees = sorted(set(row["ID"] for row in rows))
days = sorted(set(row["date"].strftime("%Y-%m-%d") for row in rows))
shifts = sorted(set((format_time(row["start_time"]), format_time(row["end_time"])) for row in rows))

print("従業員:", employees)
print("日付:", days)
print("シフト時間帯:", shifts)

# --- OR-Tools モデル作成 ---
model = cp_model.CpModel()

# 変数作成（誰がどの日にどの時間帯に入るか）
x = {}
for e in employees:
    for d in days:
        for s in shifts:
            x[(e, d, s)] = model.NewBoolVar(f"x_{e}_{d}_{s}")

# --- 制約①：同じ日・同じ時間帯に入れるのは1人まで ---
for d in days:
    for s in shifts:
        model.Add(sum(x[(e, d, s)] for e in employees) <= 2)

# --- 制約②：1人は1日に1シフトまで ---
for e in employees:
    for d in days:
        model.Add(sum(x[(e, d, s)] for s in shifts) <= 1)

# --- 目的関数（できるだけ多くシフトを埋める） ---
model.Maximize(sum(x[(e, d, s)] for e in employees for d in days for s in shifts))

# --- 求解 ---
solver = cp_model.CpSolver()
status = solver.Solve(model)

# --- 結果表示 ---
if status == cp_model.OPTIMAL:
    print("\n=== シフト自動作成結果 ===")
    for d in days:
        print(f"\n【{d}】")
        for s in shifts:
            start, end = s
            assigned = False
            for e in employees:
                if solver.Value(x[(e, d, s)]) == 1:
                    print(f" {e}：{start}〜{end}")
                    assigned = True
            if not assigned:
                print(f" （{start}〜{end}）→ 空き")
else:
    print("⚠️ 解が見つかりませんでした。")

cursor.close()
conn.close()
