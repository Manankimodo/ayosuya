from flask import Blueprint, render_template, jsonify, request, redirect, url_for
import mysql.connector
from datetime import datetime, timedelta, time as time_cls, date as date_cls
from ortools.sat.python import cp_model
import random, traceback

# ブループリントの定義
makeshift_bp = Blueprint('makeshift', __name__, url_prefix='/makeshift')


# === ユーティリティ関数 ===

# DB接続
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="ayosuya"
    )

# 時刻フォーマット変換
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

# datetime.timeオブジェクトへの変換を保証
def ensure_time_obj(v):
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
    return datetime.strptime("00:00:00", "%H:%M:%S").time()

# timedelta, time_cls, strをHH:MM:SS文字列に変換
def to_time_str(v):
    if isinstance(v, timedelta):
        total_seconds = int(v.total_seconds())
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        return f"{h:02d}:{m:02d}:00"
    elif isinstance(v, str):
        return v
    elif isinstance(v, time_cls):
        return v.strftime("%H:%M:%S")
    elif isinstance(v, datetime):
        return v.time().strftime("%H:%M:%S")
    else:
        return "00:00:00"

# 空き時間を計算
def find_free_times(registered_times):
    """1日の中の空き時間を返す（出勤がない時間帯を全て出す）"""
    full_day_start = datetime.strptime("00:00", "%H:%M")
    full_day_end = datetime.strptime("23:59", "%H:%M")

    if not registered_times:
        return [(full_day_start.strftime("%H:%M"), full_day_end.strftime("%H:%M"))]

    intervals = []
    for s, e in registered_times:
        try:
            start = datetime.strptime(s, "%H:%M")
            end = datetime.strptime(e, "%H:%M")
            if start < end:
                intervals.append((start, end))
        except Exception:
            continue

    intervals.sort()
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

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
    
    # calendarテーブルから希望シフトを取得
    cursor.execute("SELECT ID, date, start_time, end_time FROM calendar ORDER BY date, start_time")
    rows = cursor.fetchall()
    
    # shift_tableから確定シフトを取得 (表示用)
    cursor.execute("SELECT user_id, date, start_time, end_time, type FROM shift_table ORDER BY date, start_time")
    confirmed_shifts = cursor.fetchall()

    cursor.close()
    conn.close()

    if not rows:
        return render_template("admin.html", results=[], confirmed_shifts=[])

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

    # 確定シフトのフォーマット
    formatted_confirmed = []
    for shift in confirmed_shifts:
        formatted_confirmed.append({
            "date": shift["date"].strftime("%Y-%m-%d"),
            "user_id": shift["user_id"],
            "start_time": format_time(shift["start_time"]),
            "end_time": format_time(shift["end_time"]),
            "type": shift["type"]
        })
        
    return render_template("admin.html", results=results, confirmed_shifts=formatted_confirmed)


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

    all_registered = [
        slot for slots in user_dict.values() for slot in slots if slot[0] != "出勤できない"
    ]
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


# === 自動生成ロジック ===
# ... (makeshift_bp.route("/generate") の定義まで省略) ...

# === 自動生成ロジック（希望スコア最大化ロジックを統合） ===
# ... (makeshift_bp.route("/generate") の定義まで省略) ...

# === 自動生成ロジック（希望時刻絶対優先ロジックを統合） ===
# ... (makeshift_bp.route("/generate") の定義まで省略) ...

# === 自動生成ロジック（複合目標関数に修正） ===
@makeshift_bp.route("/auto_calendar")
def auto_calendar():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # --- 1. 設定取得 ---
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

    if settings.get("max_people_per_shift", 0) < 1:
        settings["max_people_per_shift"] = 1
    if settings.get("interval_minutes", 0) <= 0:
        settings["interval_minutes"] = 60

    # --- 2. 希望取得 ---
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

    cursor.execute("DELETE FROM shift_table")
    conn.commit()

    days = sorted(set(r["date"] for r in rows))
    result_all = []

    # --- 3. 日ごとのシフト生成（CP-SAT）---
    for day in days:
        try:
            print(f"\n--- {day} の処理開始 ---")
            day_requests = [r for r in rows if r["date"] == day]
            users = list({str(r["user_id"]) for r in day_requests if r.get("user_id") is not None})

            if not users:
                continue

            shift_start = datetime.strptime(to_time_str(settings["start_time"]), "%H:%M:%S")
            shift_end = datetime.strptime(to_time_str(settings["end_time"]), "%H:%M:%S")
            interval = timedelta(minutes=settings["interval_minutes"])
            interval_minutes = settings["interval_minutes"]

            # timeslots 作成
            timeslots = []
            current = shift_start
            while current + interval <= shift_end:
                timeslots.append((current, current + interval))
                current += interval
            if not timeslots:
                timeslots = [(shift_start, shift_end if shift_end > shift_start else shift_start + timedelta(hours=1))]

            # モデル
            model = cp_model.CpModel()
            x = {(u, t): model.NewBoolVar(f"x_{u}_{t}") for u in users for t in range(len(timeslots))}

            # 制約1: 人数制限 (ハード制約)
            for t in range(len(timeslots)):
                model.Add(sum(x[(u, t)] for u in users) <= settings["max_people_per_shift"])

            # --- 勤務連続性制約と総勤務時間の定義 (ハード制約) ---
            has_shift = {u: model.NewBoolVar(f"has_shift_{u}") for u in users}
            total_work = {u: model.NewIntVar(0, len(timeslots), f"total_{u}") for u in users}
            slot_indices = list(range(len(timeslots)))
            
            for u in users:
                # has_shift と total_work の定義
                model.Add(sum(x[(u, t)] for t in range(len(timeslots))) >= 1).OnlyEnforceIf(has_shift[u])
                model.Add(sum(x[(u, t)] for t in range(len(timeslots))) == 0).OnlyEnforceIf(has_shift[u].Not())
                model.Add(total_work[u] == sum(x[(u, t)] for t in range(len(timeslots))))

                # 勤務の連続性 (ハード制約)
                active_indices = [t for t in slot_indices if (u, t) in x]
                if active_indices:
                    active_start = model.NewIntVar(0, len(timeslots) - 1, f"active_start_{u}")
                    active_end = model.NewIntVar(0, len(timeslots) - 1, f"active_end_{u}")
                    
                    model.AddMinEquality(active_start, active_indices).OnlyEnforceIf(has_shift[u])
                    model.AddMaxEquality(active_end, active_indices).OnlyEnforceIf(has_shift[u])
                    
                    total_slots_span = model.NewIntVar(0, len(timeslots), f"span_{u}")
                    model.Add(total_slots_span == active_end - active_start + 1).OnlyEnforceIf(has_shift[u])
                    model.Add(total_work[u] == total_slots_span).OnlyEnforceIf(has_shift[u])
            
            # --- 複合目標関数の定義 ---
            
            # 希望スロットを定義（全モードで利用）
            user_pref_slots = {}
            for u in users:
                user_pref_slots[u] = set()
                u_requests = [r for r in day_requests if str(r.get("user_id")) == u]
                
                for r in u_requests:
                    try:
                        req_start = datetime.combine(datetime.today(), ensure_time_obj(r["start_time"]))
                        req_end = datetime.combine(datetime.today(), ensure_time_obj(r["end_time"]))
                        
                        for t, (s, e) in enumerate(timeslots):
                            # 希望開始時間 s から 希望終了時間 e までのスロットを希望スロットとする
                            if s >= req_start and e <= req_end:
                                user_pref_slots[u].add(t)
                    except Exception:
                        continue
            
            # スコアリングとペナルティ (balanceモード用)
            positive_score_terms = []
            negative_penalty_terms = []
            
            for u in users:
                for t in range(len(timeslots)):
                    if (u, t) in x:
                        if t in user_pref_slots[u]:
                            # 希望スロットでの勤務: +100 ポイント
                            positive_score_terms.append(x[(u, t)] * 100)
                        else:
                            # 希望外スロットでの勤務: -10000 の超ペナルティ
                            negative_penalty_terms.append(x[(u, t)] * 10000)


            # --- ✅ 目標関数をモードごとに設定 ---
            
            if settings["auto_mode"] == "balance":
                # balanceモード: (希望スコア) - (希望外ペナルティ) の最大化
                model.Maximize(sum(positive_score_terms) - sum(negative_penalty_terms))
            
            else: # "random" モードを含むその他のモードの場合
                # randomモード: 勤務時間（スロット数）の総和を最大化
                total_slots_sum = sum(total_work[u] for u in users)
                model.Maximize(total_slots_sum)


            # --- 最小・最大勤務時間制約 (ハード制約) ---
            min_slots = int(settings["min_hours_per_day"] * 60 / interval_minutes)
            global_max_slots = int(settings["max_hours_per_day"] * 60 / interval_minutes)

            user_max_slots = {}
            for u in users:
                # ユーザーの希望総時間に基づいて、最大スロット数を計算
                total_requested_minutes = sum((datetime.combine(datetime.today(), ensure_time_obj(r["end_time"])) - datetime.combine(datetime.today(), ensure_time_obj(r["start_time"]))).total_seconds() / 60
                                              for r in [r for r in day_requests if str(r.get("user_id")) == u and datetime.combine(datetime.today(), ensure_time_obj(r["end_time"])) > datetime.combine(datetime.today(), ensure_time_obj(r["start_time"]))])
                max_slots_based_on_request = int(total_requested_minutes / interval_minutes)
                user_max_slots[u] = min(max_slots_based_on_request, global_max_slots)

            for u in users:
                # 勤務が割り当てられた場合のみ、最小時間を強制
                model.Add(total_work[u] >= min_slots).OnlyEnforceIf(has_shift[u])
                # 勤務時間は、設定と希望の範囲内であること
                model.Add(total_work[u] <= user_max_slots[u])
                
            # ソルバー実行
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 10
            
            # ソルバー探索パラメータの調整
            solver.parameters.random_seed = random.randint(0, 1000)
            solver.parameters.num_workers = 4
            
            status = solver.Solve(model)
            print("  Solver Status:", solver.StatusName(status))

            inserted_any = False

            # --- 4. SOLUTION 登録 (連続スロット結合ロジック) ---
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                
                user_slots = {u: [] for u in users}
                for u in users:
                    for t in range(len(timeslots)):
                        if (u, t) in x and solver.Value(x[(u, t)]) == 1:
                            user_slots[u].append(t)
                
                # 連続するスロットを結合し、シフトとして登録
                for u, slots in user_slots.items():
                    if not slots:
                        continue
                    
                    slots.sort()
                    merged_shifts = []
                    
                    current_start_index = slots[0]
                    current_end_index = slots[0]
                    
                    for i in range(1, len(slots)):
                        if slots[i] == current_end_index + 1:
                            current_end_index = slots[i]
                        else:
                            merged_shifts.append((current_start_index, current_end_index))
                            current_start_index = slots[i]
                            current_end_index = slots[i]
                    
                    merged_shifts.append((current_start_index, current_end_index))

                    # 結合されたシフトをDBに挿入
                    for start_t, end_t in merged_shifts:
                        shift_start_time = timeslots[start_t][0]
                        shift_end_time = timeslots[end_t][1]
                        
                        try:
                            cursor.execute("""
                                INSERT INTO shift_table (user_id, date, start_time, end_time, type)
                                VALUES (%s, %s, %s, %s, 'work')
                            """, (u, day, shift_start_time.time(), shift_end_time.time()))
                            result_all.append({
                                "date": str(day),
                                "user_id": u,
                                "start_time": shift_start_time.strftime("%H:%M"),
                                "end_time": shift_end_time.strftime("%H:%M"),
                                "type": "work"
                            })
                            inserted_any = True
                        except Exception as ex:
                            print("  DB Insert Error (Merged):", ex)

            # --- 5. Fallbackロジック (変更なし) ---
            # ... (Fallbackロジックと休憩ロジックはそのまま維持) ...
            
            # fallback1: 希望ベースの貪欲割当
            if not inserted_any:
                print("  ⚠️ ソルバーで割り当てが行われなかったため、希望ベースで貪欲に割当を行います。")
                
                for t, (s, e) in enumerate(timeslots):
                    want_users = []
                    for r in day_requests:
                        uid = str(r["user_id"])
                        req_start = datetime.combine(datetime.today(), ensure_time_obj(r["start_time"]))
                        req_end = datetime.combine(datetime.today(), ensure_time_obj(r["end_time"]))
                        if s >= req_start and e <= req_end:
                            want_users.append(uid)
                    
                    if want_users:
                        chosen = random.sample(want_users, min(len(want_users), settings["max_people_per_shift"]))
                        for u in chosen:
                            try:
                                cursor.execute("""
                                    INSERT INTO shift_table (user_id, date, start_time, end_time, type)
                                    VALUES (%s, %s, %s, %s, 'work')
                                """, (u, day, s.time(), e.time()))
                                result_all.append({
                                    "date": str(day),
                                    "user_id": u,
                                    "start_time": s.strftime("%H:%M"),
                                    "end_time": e.strftime("%H:%M"),
                                    "type": "work"
                                })
                                inserted_any = True
                            except Exception as ex:
                                print("  DB Insert Error (fallback1):", ex)

            # fallback2: それでも無ければ、各 timeslot にランダムで割当
            if not inserted_any:
                print("  ⚠️ それでも割当なし。timeslotごとに強制割当（ランダム）を行います。")
                for t, (s, e) in enumerate(timeslots):
                    chosen = random.sample(users, min(len(users), settings["max_people_per_shift"]))
                    for u in chosen:
                        try:
                            cursor.execute("""
                                INSERT INTO shift_table (user_id, date, start_time, end_time, type)
                                VALUES (%s, %s, %s, %s, 'work')
                            """, (u, day, s.time(), e.time()))
                            result_all.append({
                                "date": str(day),
                                "user_id": u,
                                "start_time": s.strftime("%H:%M"),
                                "end_time": e.strftime("%H:%M"),
                                "type": "work"
                            })
                            inserted_any = True
                        except Exception as ex:
                            print("  DB Insert Error (fallback2):", ex)

            # 日ごとにコミット
            try:
                conn.commit()
                print(f"  {day} の登録をコミットしました。挿入件数累計: {len(result_all)}")
            except Exception as ex:
                print("  Commit Error:", ex)

        except Exception as e:
            print(f"  エラー（{day}）：", e)
            print(traceback.format_exc())

    # --- 6. 休憩追加 (変更なし) ---
    try:
        cursor.execute("""
            SELECT user_id, date, MIN(start_time) AS start_time, MAX(end_time) AS end_time
            FROM shift_table
            WHERE type = 'work'
            GROUP BY user_id, date
        """)
        work_blocks = cursor.fetchall()

        break_duration_minutes = int(settings.get("break_minutes", 60))

        for block in work_blocks:
            start_time = ensure_time_obj(block["start_time"])
            end_time = ensure_time_obj(block["end_time"])
            start = datetime.combine(block["date"], start_time)
            end = datetime.combine(block["date"], end_time)
            total_hours = (end - start).total_seconds() / 3600

            if total_hours >= 6 and break_duration_minutes > 0:
                duration = end - start
                center_point = start + (duration / 2) 
                half_break_td = timedelta(minutes=break_duration_minutes / 2)
                break_start = center_point - half_break_td
                break_end = center_point + half_break_td
                
                random_offset_minutes = random.choice([-15, -10, -5, 0, 5, 10, 15])
                random_offset_td = timedelta(minutes=random_offset_minutes)
                
                break_start += random_offset_td
                break_end += random_offset_td

                if break_start < start:
                    break_start = start
                    break_end = start + timedelta(minutes=break_duration_minutes)
                elif break_end > end:
                    break_end = end
                    break_start = end - timedelta(minutes=break_duration_minutes)
                
                try:
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
                except Exception as ex:
                    print("  DB Insert Error (break):", ex)
        conn.commit()
    except Exception as ex:
        print("  休憩生成でエラー:", ex)

    cursor.close()
    conn.close()

    print("\n✅ 全処理完了。登録件数:", len(result_all))
    return render_template(
        "auto_calendar.html",
        shifts=result_all,
        settings=settings,
        message="✅ 希望外勤務に強力なペナルティを与え、希望を最優先する自動シフトを作成しました。"
    )

# === 設定画面 ===
@makeshift_bp.route("/settings", methods=["GET", "POST"])
def settings():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # --- 現在の設定を取得 ---
    cursor.execute("SELECT ID, start_time, end_time, break_minutes, interval_minutes, max_hours_per_day, min_hours_per_day, max_people_per_shift, auto_mode FROM shift_settings LIMIT 1")
    settings = cursor.fetchone()

    # --- データが存在しない場合の初期値 ---
    if not settings:
        settings = {
            "ID": None,
            "start_time": "09:00",
            "end_time": "18:00",
            "break_minutes": 60,
            "interval_minutes": 60,
            "max_hours_per_day": 8,
            "min_hours_per_day": 4,
            "max_people_per_shift": 3,
            "auto_mode": "balance",
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

        # 既存データを確認
        cursor.execute("SELECT ID FROM shift_settings LIMIT 1")
        existing_id = cursor.fetchone()

        if existing_id:
            # データが存在する場合: UPDATE
            cursor.execute("""
                UPDATE shift_settings
                SET start_time=%s, end_time=%s, break_minutes=%s, interval_minutes=%s,
                    max_hours_per_day=%s, min_hours_per_day=%s, max_people_per_shift=%s,
                    auto_mode=%s, updated_at=NOW()
                WHERE ID = %s
            """, (
                start_time, end_time, break_minutes, interval_minutes,
                max_hours_per_day, min_hours_per_day, max_people_per_shift, auto_mode, existing_id["ID"]
            ))
        else:
            # データが存在しない場合: INSERT
            cursor.execute("""
                INSERT INTO shift_settings 
                (start_time, end_time, break_minutes, interval_minutes, max_hours_per_day, min_hours_per_day, max_people_per_shift, auto_mode, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                start_time, end_time, break_minutes, interval_minutes,
                max_hours_per_day, min_hours_per_day, max_people_per_shift, auto_mode
            ))
            
        conn.commit()
        conn.close()
        return redirect(url_for("makeshift.settings"))

    conn.close()

    # --- 🕒 GET時の時刻表示フォーマット ---
    for key in ["start_time", "end_time"]:
        if settings[key]:
            settings[key] = str(settings[key])[:5]
        else:
            settings[key] = "09:00" if key == "start_time" else "18:00"

    return render_template("shift_setting.html", settings=settings)