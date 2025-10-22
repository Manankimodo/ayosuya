from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from ortools.sat.python import cp_model
from extensions import db  # ✅ extensions から import

makeshift_bp = Blueprint('makeshift', __name__, url_prefix='/makeshift')
# データ定義
employees = ['佐藤', '鈴木', '高橋']
days = ['月', '火', '水', '木']

# 希望シフト
requests = {
    ('佐藤', '月'): 1,
    ('佐藤', '火'): 1,
    ('鈴木', '火'): 1,
    ('鈴木', '水'): 1,
    ('高橋', '水'): 1,
    ('高橋', '木'): 1,
}

# モデル作成
model = cp_model.CpModel()

# 各従業員 × 日 の変数（勤務するなら1、休みなら0）
work = {}
for e in employees:
    for d in days:
        work[(e, d)] = model.NewBoolVar(f'{e}_{d}')

# 制約① 各日にはちょうど1人
for d in days:
    model.Add(sum(work[(e, d)] for e in employees) == 1)

# 制約② 各従業員の勤務回数が均等に近いように
min_shifts = len(days) // len(employees)
max_shifts = min_shifts + 1
for e in employees:
    model.Add(sum(work[(e, d)] for d in days) >= min_shifts)
    model.Add(sum(work[(e, d)] for d in days) <= max_shifts)

# 目的関数：希望日をできるだけ満たす（希望=1なら加点）
model.Maximize(
    sum(requests.get((e, d), 0) * work[(e, d)] for e in employees for d in days)
)

# ソルバー実行
solver = cp_model.CpSolver()
status = solver.Solve(model)

# 結果出力
if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
    print("✅ シフト割り当て結果：\n")
    for d in days:
        for e in employees:
            if solver.Value(work[(e, d)]) == 1:
                print(f"{d}: {e}")
else:
    print("❌ 解が見つかりませんでした。")
