from flask import Blueprint, render_template, jsonify, request, redirect, url_for,flash
import mysql.connector
from line_notifier import send_help_request_to_staff
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
# === ユーティリティ関数 (修正案) ===
# ... (他のコードはそのまま) ...
# 時刻フォーマット変換
def format_time(value):
    """MySQL TIME型 (timedelta, time, or str) → HH:MM形式に変換"""
    if not value:
        return None
    if isinstance(value, str):
        return value[:5]
    elif hasattr(value, "seconds"): # timedelta の処理
        total_seconds = value.seconds
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"
    # ✅ 追加: datetime.time オブジェクトの場合の処理
    elif isinstance(value, time_cls):
        return value.strftime("%H:%M")
    
    return None
# ... (他のコードはそのまま) ...

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
    return redirect(url_for('makeshift.show_admin_shift'))




# === 自動生成ロジック（複合目標関数に修正） ===----------------------------------------------------------------------
from ortools.sat.python import cp_model
from datetime import datetime, time as time_cls, timedelta, date as date_cls
import traceback
from flask import jsonify, render_template



# 'balance'モードの場合に、勤務時間の公平性を評価するためのペナルティ重み
FAIRNESS_PENALTY_WEIGHT = 100
# 'preference'モードの場合に、希望充足度を最大化するための重み
PREFERENCE_REWARD_WEIGHT = 1000  



# ==========================================
# 1. シフト自動生成ロジック (メイン機能)
# ==========================================
# makeshift.py の auto_calendar 関数をこれに置き換えてください

@makeshift_bp.route("/auto_calendar")
def auto_calendar():
    from datetime import time, datetime, timedelta 
    import traceback

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # ★★★ 時間を安全に文字列変換する関数を追加 ★★★
        def safe_time_format(val):
            if val is None:
                return "00:00"
            if hasattr(val, 'strftime'):
                return val.strftime("%H:%M")
            if hasattr(val, 'total_seconds'):
                total_seconds = int(val.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                return f"{hours:02d}:{minutes:02d}"
            s = str(val)
            if ':' in s:
                return s[:5]
            return "00:00"
        
        # 0. 設定取得
        cursor.execute("SELECT * FROM shift_settings LIMIT 1")
        row = cursor.fetchone()
        
        settings = {
            "start_time": "09:00", "end_time": "22:00", "break_minutes": 60,
            "interval_minutes": 15, "max_hours_per_day": 8, "min_hours_per_day": 0,
            "max_people_per_shift": 30, "auto_mode": "balance"
        }
        if row:
            settings.update({
                "start_time": safe_time_format(row["start_time"]),  # ★ここを修正
                "end_time": safe_time_format(row["end_time"]),      # ★ここを修正
                "break_minutes": row.get("break_minutes", 60),
                "interval_minutes": row.get("interval_minutes", 15),
                "max_hours_per_day": row.get("max_hours_per_day", 8),
                "min_hours_per_day": row.get("min_hours_per_day", 0),
                "max_people_per_shift": row.get("max_people_per_shift", 30),
                "auto_mode": row.get("auto_mode", "balance")
            })

        def safe_to_time(val):
            if val is None: return time(0, 0)
            if isinstance(val, time): return val
            if isinstance(val, timedelta): return (datetime.min + val).time()
            s = str(val).strip()
            try: return datetime.strptime(s, "%H:%M:%S").time()
            except: pass
            try: return datetime.strptime(s, "%H:%M").time()
            except: pass
            return time(0, 0)

        SHIFT_START = safe_to_time(settings['start_time'])
        SHIFT_END = safe_to_time(settings['end_time'])
        INTERVAL_MINUTES = int(settings['interval_minutes'])
        settings['start_time'] = SHIFT_START.strftime("%H:%M")  # ★JSONに渡す前に再度文字列化
        settings['end_time'] = SHIFT_END.strftime("%H:%M")      # ★JSONに渡す前に再度文字列化

        # ... 以下のコードは変更なし
        cursor.execute("SELECT ID, name FROM account")
        users_data = cursor.fetchall()
        user_ids = [str(u['ID']) for u in users_data]
        num_users = len(user_ids)
        user_map = {str(user_id): i for i, user_id in enumerate(user_ids)}
        
        position_names = {}
        cursor.execute("SELECT id, name FROM positions")
        for p in cursor.fetchall(): position_names[str(p['id'])] = p['name']

        user_skill_ids = {}
        cursor.execute("SELECT user_id, position_id FROM user_positions")
        for row in cursor.fetchall():
            uid = str(row['user_id'])
            pid = str(row['position_id'])
            if uid not in user_skill_ids: user_skill_ids[uid] = []
            user_skill_ids[uid].append(pid)
            
                # 修正後
        # ★★★ 平日と土日祝の需要データを分けて取得 ★★★
        demand_weekday = {}
        demand_weekend = {}

        cursor.execute("SELECT time_slot, position_id, required_count, day_type FROM shift_demand")
        for row in cursor.fetchall():
            t_str = safe_to_time(row['time_slot']).strftime("%H:%M")
            pid = str(row['position_id'])
            day_type = row.get('day_type', 'weekday')
            
            if day_type == 'weekday':
                if t_str not in demand_weekday: demand_weekday[t_str] = {}
                demand_weekday[t_str][pid] = row['required_count']
            else:  # weekend
                if t_str not in demand_weekend: demand_weekend[t_str] = {}
                demand_weekend[t_str][pid] = row['required_count']

        cursor.execute("SELECT DISTINCT date FROM calendar WHERE work = 1 ORDER BY date")
        target_dates = [row['date'] for row in cursor.fetchall()]
        cursor.execute("DELETE FROM shift_table")
        conn.commit()
        
        all_generated_shifts = []
        # ★ここ重要: 不足リストはここで宣言せず、日付ごとのループ内で処理します

        if not target_dates:
             conn.close()
             return render_template("auto_calendar.html", message="希望シフトなし", shifts=[], settings=settings)

        for target_date_obj in target_dates:
            target_date_str = target_date_obj.strftime("%Y-%m-%d")
            
            # ★★★ 曜日を判定（0=月曜, 6=日曜） ★★★
            weekday = target_date_obj.weekday()
            is_weekend = weekday >= 5  # 土曜(5)、日曜(6)
            
            # ★★★ 適切な需要マップを選択 ★★★
            demand_map = demand_weekend if is_weekend else demand_weekday
            
            cursor.execute("SELECT ID, start_time, end_time FROM calendar WHERE date = %s AND work = 1", (target_date_str,))
            preference_rows = cursor.fetchall()
            
            time_intervals = []
            base_date = datetime(2000, 1, 1)
            current_dt = base_date.replace(hour=SHIFT_START.hour, minute=SHIFT_START.minute)
            target_end_dt = base_date.replace(hour=SHIFT_END.hour, minute=SHIFT_END.minute)
            
            while current_dt < target_end_dt:
                time_intervals.append(current_dt.time())
                current_dt += timedelta(minutes=INTERVAL_MINUTES)
            num_intervals = len(time_intervals)
            if num_intervals == 0: continue 

            model = cp_model.CpModel()
            shifts = {}
            for u in range(num_users):
                for t in range(num_intervals):
                    shifts[u, t] = model.NewBoolVar(f's_{u}_{t}')
            
            # 制約設定
            demand_fulfillment = []
            for t_idx, t_time in enumerate(time_intervals):
                t_str = t_time.strftime("%H:%M")
                total_req = 0
                if t_str in demand_map:
                    current_demand = demand_map[t_str]
                    needed_pids = [pid for pid, cnt in current_demand.items() if cnt > 0]
                    for u_idx in range(num_users):
                        user_id = user_ids[u_idx]
                        user_skills = user_skill_ids.get(user_id, [])
                        if needed_pids and not any(pid in needed_pids for pid in user_skills):
                            model.Add(shifts[u_idx, t_idx] == 0)
                    for pid, count in current_demand.items():
                        total_req += count
                        capable = [shifts[u, t_idx] for u in range(num_users) if pid in user_skill_ids.get(user_ids[u], [])]
                        if capable:
                            model.Add(sum(capable) <= count)
                            demand_fulfillment.append(sum(capable))
                model.Add(sum(shifts[u, t_idx] for u in range(num_users)) <= total_req)

                # ★★★ ---------------------------------------------------------------------- ★★★
            max_hours = float(settings['max_hours_per_day'])
            max_intervals = int((max_hours * 60) / INTERVAL_MINUTES)

            for u in range(num_users):
                model.Add(sum(shifts[u, t] for t in range(num_intervals)) <= max_intervals)
            # ★★★ --------------------------------------------------------------------------- ★★★

            users_with_pref = {str(row['ID']) for row in preference_rows}
            for u, uid in enumerate(user_ids):
                if str(uid) not in users_with_pref:
                    for t in range(num_intervals): model.Add(shifts[u, t] == 0)

            users_with_pref = {str(row['ID']) for row in preference_rows}
            for u, uid in enumerate(user_ids):
                if str(uid) not in users_with_pref:
                    for t in range(num_intervals): model.Add(shifts[u, t] == 0)
            
            pref_score = []
            for row in preference_rows:
                uid_str = str(row['ID'])
                if uid_str not in user_map: continue
                u = user_map[uid_str]
                s_val = safe_to_time(row['start_time'])
                e_val = safe_to_time(row['end_time'])
                for t, t_val in enumerate(time_intervals):
                    if s_val <= t_val < e_val: pref_score.append(shifts[u, t])
                    else: model.Add(shifts[u, t] == 0)

            model.Maximize(sum(demand_fulfillment)*10 + sum(pref_score))
            solver = cp_model.CpSolver()
            status = solver.Solve(model)
            
            if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                user_assigned_roles = {}
                
                # =========================================================
                # ★★★ 新・不足計算ロジック（作りながら結合） ★★★
                # =========================================================
                # 継続中の不足を記録する辞書: Key=(役割ID, 何人目), Value=データ
                active_shortages = {} 
                shortage_list_day = []

                for t_idx, t_time in enumerate(time_intervals):
                    t_str = t_time.strftime("%H:%M")
                    
                    # 1. 勤務者の役割割り当て
                    working_users = []
                    for u_idx in range(num_users):
                        if solver.Value(shifts[u_idx, t_idx]) == 1:
                            working_users.append(u_idx)
                    
                    open_slots = []
                    if t_str in demand_map:
                        for pid, count in demand_map[t_str].items():
                            for _ in range(count): open_slots.append(pid)
                    
                    working_users.sort(key=lambda u: len([p for p in user_skill_ids.get(user_ids[u], []) if p in open_slots]))
                    assigned_pids = {} 
                    for u_idx in working_users:
                        uid = user_ids[u_idx]
                        skills = user_skill_ids.get(uid, [])
                        filled = False
                        for i, slot_pid in enumerate(open_slots):
                            if slot_pid in skills:
                                assigned_pids[u_idx] = slot_pid
                                open_slots.pop(i)
                                filled = True
                                break
                        if not filled:
                            assigned_pids[u_idx] = skills[0] if skills else "Staff"

                    for u_idx in working_users:
                        role_name = position_names.get(assigned_pids.get(u_idx), "Work")
                        if u_idx not in user_assigned_roles: user_assigned_roles[u_idx] = {}
                        user_assigned_roles[u_idx][t_idx] = role_name

                    # 2. 不足の記録（ここで結合しながら作成）
                    current_step_shortage_keys = set()
                    slot_counts = {}
                    for pid in open_slots:
                        slot_counts[pid] = slot_counts.get(pid, 0) + 1
                    
                    for pid, count in slot_counts.items():
                        p_name = position_names.get(pid, "役割")
                        for i in range(count):
                            key = (pid, i) # (役割ID, 何人目か)
                            current_step_shortage_keys.add(key)
                            
                            next_end_dt = datetime.combine(base_date, t_time) + timedelta(minutes=INTERVAL_MINUTES)
                            next_end_str = next_end_dt.time().strftime("%H:%M")

                            if key in active_shortages:
                                # 継続中：終了時間を延長
                                active_shortages[key]['end_time'] = next_end_str
                            else:
                                # 新規発生：登録
                                neg_id = -1 * (int(pid) * 1000 + i)
                                unique_name = f"🚨 {p_name}不足 ({i+1})"
                                active_shortages[key] = {
                                    "user_id": neg_id,
                                    "user_name": unique_name,
                                    "date": target_date_str,
                                    "start_time": t_time.strftime("%H:%M"),
                                    "end_time": next_end_str,
                                    "type": unique_name
                                }
                    
                    # なくなった不足（解決した不足）を確定リストへ移動
                    completed_keys = []
                    for key in active_shortages:
                        if key not in current_step_shortage_keys:
                            shortage_list_day.append(active_shortages[key])
                            completed_keys.append(key)
                    for key in completed_keys:
                        del active_shortages[key]

                # 日付ループ終了後、残っている継続中データを確定
                for item in active_shortages.values():
                    shortage_list_day.append(item)
                
                # 不足データを全体リストへ追加（ソートなどは不要、すでに一本化済み）
                all_generated_shifts.extend(shortage_list_day)

                # スタッフのシフト結合
                for u_idx, roles_map in user_assigned_roles.items():
                    user_id = user_ids[u_idx]
                    current_block_start = None
                    current_role = None
                    for t_idx in range(num_intervals):
                        role_name = roles_map.get(t_idx)
                        t_time = time_intervals[t_idx]
                        if role_name:
                            if current_block_start is None:
                                current_block_start = t_time
                                current_role = role_name
                            elif role_name != current_role:
                                end_dt_calc = datetime.combine(base_date, t_time)
                                all_generated_shifts.append({
                                    "user_id": user_id, "date": target_date_str,
                                    "start_time": current_block_start.strftime("%H:%M"),
                                    "end_time": end_dt_calc.time().strftime("%H:%M"), "type": current_role
                                })
                                current_block_start = t_time
                                current_role = role_name
                        else:
                            if current_block_start is not None:
                                end_dt_calc = datetime.combine(base_date, time_intervals[t_idx])
                                all_generated_shifts.append({
                                    "user_id": user_id, "date": target_date_str,
                                    "start_time": current_block_start.strftime("%H:%M"),
                                    "end_time": end_dt_calc.time().strftime("%H:%M"), "type": current_role
                                })
                                current_block_start = None
                                current_role = None
                    if current_block_start is not None:
                        last_t = time_intervals[-1]
                        last_end_dt = datetime.combine(base_date, last_t) + timedelta(minutes=INTERVAL_MINUTES)
                        all_generated_shifts.append({
                            "user_id": user_id, "date": target_date_str,
                            "start_time": current_block_start.strftime("%H:%M"),
                            "end_time": last_end_dt.time().strftime("%H:%M"), "type": current_role
                        })

        # makeshift.py の auto_calendar 関数の最後の方
        
        final_display_shifts = []
        if all_generated_shifts:
            sql = "INSERT INTO shift_table (user_id, date, start_time, end_time, type) VALUES (%s, %s, %s, %s, %s)"
            data = [(s['user_id'], s['date'], s['start_time'], s['end_time'], s['type']) for s in all_generated_shifts]
            cursor.executemany(sql, data)
            conn.commit()
            
            # 再取得して表示
            cursor.execute("""
                SELECT s.user_id, a.name as user_name, s.date, s.start_time, s.end_time, s.type 
                FROM shift_table s LEFT JOIN account a ON s.user_id = a.ID 
                ORDER BY s.user_id, s.date, s.start_time
            """)
            raw_shifts = cursor.fetchall()
            
            # 最終整形（念のための再結合）
            if raw_shifts:
                curr = raw_shifts[0]
                # 時間を文字列化
                curr['start_time'] = safe_to_time(curr['start_time']).strftime("%H:%M")
                curr['end_time'] = safe_to_time(curr['end_time']).strftime("%H:%M")
                curr['date'] = str(curr['date'])
                
                # ★修正ポイント1: int() で囲んで数値に変換してから比較
                if int(curr['user_id']) < 0: 
                    curr['user_name'] = curr['type']

                for i in range(1, len(raw_shifts)):
                    nxt = raw_shifts[i]
                    nxt['start_time'] = safe_to_time(nxt['start_time']).strftime("%H:%M")
                    nxt['end_time'] = safe_to_time(nxt['end_time']).strftime("%H:%M")
                    nxt['date'] = str(nxt['date'])
                    
                    # ★修正ポイント2: ここも int() で囲む
                    if int(nxt['user_id']) < 0: 
                        nxt['user_name'] = nxt['type'] # 名前補完

                    if (curr['user_id'] == nxt['user_id'] and curr['date'] == nxt['date'] and 
                        curr['type'] == nxt['type'] and curr['end_time'] == nxt['start_time']):
                        curr['end_time'] = nxt['end_time']
                    else:
                        final_display_shifts.append(curr)
                        curr = nxt
                final_display_shifts.append(curr)

        conn.close()
        return render_template("auto_calendar.html", settings=settings, shifts=final_display_shifts, message=f"{len(final_display_shifts)}件表示")

    except Exception as e:
        conn.close()
        print(traceback.format_exc()) # エラー詳細をコンソールに出す
        return render_template("auto_calendar.html", settings=settings if 'settings' in locals() else {}, shifts=[], message=f"エラー: {str(e)}")#-------------------------------------------------------------------------------------------------------------
# ==========================================
# 2. 設定画面の表示と基本設定の更新
# ==========================================
@makeshift_bp.route("/settings", methods=["GET", "POST"])
def settings():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # --- POST: 設定更新処理 ---
        if request.method == "POST":
            start_time = request.form.get("start_time")
            end_time = request.form.get("end_time")
            break_minutes = request.form.get("break_minutes", 60)
            interval_minutes = request.form.get("interval_minutes", 15)
            max_hours_per_day = request.form.get("max_hours_per_day", 8)
            min_hours_per_day = request.form.get("min_hours_per_day", 0)
            max_people_per_shift = request.form.get("max_people_per_shift", 30)
            auto_mode = request.form.get("auto_mode", "balance")

            cursor.execute("SELECT ID FROM shift_settings LIMIT 1")
            existing_id = cursor.fetchone()

            if existing_id:
                cursor.execute("""
                    UPDATE shift_settings
                    SET start_time=%s, end_time=%s, break_minutes=%s, interval_minutes=%s,
                        max_hours_per_day=%s, min_hours_per_day=%s, max_people_per_shift=%s,
                        auto_mode=%s, updated_at=NOW()
                    WHERE ID = %s
                """, (start_time, end_time, break_minutes, interval_minutes,
                      max_hours_per_day, min_hours_per_day, max_people_per_shift, auto_mode, existing_id["ID"]))
            else:
                cursor.execute("""
                    INSERT INTO shift_settings 
                    (start_time, end_time, break_minutes, interval_minutes, max_hours_per_day, min_hours_per_day, max_people_per_shift, auto_mode, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (start_time, end_time, break_minutes, interval_minutes,
                      max_hours_per_day, min_hours_per_day, max_people_per_shift, auto_mode))
            conn.commit()
            flash("✅ 基本設定を保存しました", "success")
            return redirect(url_for("makeshift.settings"))

        # --- GET: 画面表示処理 ---
        
        # 1. 基本設定
        cursor.execute("SELECT * FROM shift_settings LIMIT 1")
        settings_data = cursor.fetchone()
        if not settings_data:
            settings_data = {
                "start_time": "00:00", "end_time": "23:59", "break_minutes": 60,
                "interval_minutes": 15, "max_hours_per_day": 8, "min_hours_per_day": 0,
                "max_people_per_shift": 30, "auto_mode": "balance"
            }
        else:
            # ★★★ 時間を安全に文字列変換する関数を使用 ★★★
            def safe_time_format(val):
                if val is None:
                    return "00:00"
                # datetime.time オブジェクトの場合
                if hasattr(val, 'strftime'):
                    return val.strftime("%H:%M")
                # timedelta オブジェクトの場合
                if hasattr(val, 'total_seconds'):
                    total_seconds = int(val.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    return f"{hours:02d}:{minutes:02d}"
                # 文字列の場合
                s = str(val)
                if ':' in s:
                    return s[:5]  # "HH:MM:SS" → "HH:MM"
                return "00:00"
            
            settings_data["start_time"] = safe_time_format(settings_data["start_time"])
            settings_data["end_time"] = safe_time_format(settings_data["end_time"])

        # 2. 役割リスト
        cursor.execute("SELECT * FROM positions")
        positions_list = cursor.fetchall()
        
        # 3. 需要リスト（表示用）
        cursor.execute("""
            SELECT d.time_slot, d.position_id, d.required_count, d.day_type, p.name as position_name
            FROM shift_demand d
            LEFT JOIN positions p ON d.position_id = p.id
            ORDER BY d.day_type, d.time_slot, d.position_id
        """)
        raw_demands = cursor.fetchall()

        # ★★★ 平日と土日祝に分ける ★★★
        weekday_demands = []
        holiday_demands = []

        for r in raw_demands:
            ts_str = safe_time_format(r['time_slot'])
            if r['required_count'] > 0:
                demand_item = {
                    'time_slot': ts_str,
                    'position_id': r['position_id'],
                    'position_name': r['position_name'] or "不明",
                    'required_count': r['required_count']
                }
                
                day_type = r.get('day_type', 'weekday')
                if day_type == 'holiday':
                    holiday_demands.append(demand_item)
                else:
                    weekday_demands.append(demand_item)

        return render_template("shift_setting.html", 
            settings=settings_data, 
            positions=positions_list, 
            weekday_demands=weekday_demands,  # ★変更
            holiday_demands=holiday_demands)   # ★追加
    except Exception as e:
        print(f"Settings Error: {e}")
        import traceback
        traceback.print_exc()  # ★デバッグ用：詳細なエラーを表示
        return f"Error: {e}", 500
    finally:
        conn.close()
# ==========================================
# 3. 需要（ピークタイム）を追加する処理 (修正版: 平日/土日祝対応)
# ==========================================
@makeshift_bp.route("/settings/demand/add", methods=["POST"])
def add_demand():
    from datetime import datetime, timedelta
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        start_str = request.form.get("start_time")
        end_str = request.form.get("end_time")
        pos_id = request.form.get("position_id")
        count = int(request.form.get("required_count"))
        day_type = request.form.get("day_type", "weekday")  # ★追加: weekday or weekend
        
        fmt = "%H:%M"
        start_dt = datetime.strptime(start_str, fmt)
        end_dt = datetime.strptime(end_str, fmt)
        
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)
            
        current = start_dt
        while current < end_dt:
            time_val = current.strftime(fmt)
            
            # ★修正: day_typeも条件に追加
            cursor.execute("""
                DELETE FROM shift_demand 
                WHERE time_slot = %s AND position_id = %s AND day_type = %s
            """, (time_val, pos_id, day_type))
            
            if count > 0:
                # ★修正: day_typeも保存
                cursor.execute("""
                    INSERT INTO shift_demand (time_slot, position_id, required_count, day_type)
                    VALUES (%s, %s, %s, %s)
                """, (time_val, pos_id, count, day_type))
            
            current += timedelta(minutes=15)
            
        conn.commit()
        day_type_label = "平日" if day_type == "weekday" else "土日祝"
        flash(f"✅ {day_type_label} {start_str}〜{end_str} の設定を保存しました！", "success")
        
    except Exception as e:
        conn.rollback()
        print(e)
        flash("保存に失敗しました", "danger")
    finally:
        conn.close()
    
    return redirect(url_for('makeshift.settings') + '#demand-section')
# ==========================================
# 4. 需要をリセット（全削除）する処理
# ==========================================
@makeshift_bp.route("/settings/demand/reset", methods=["POST"])
def reset_demand():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM shift_demand")
        conn.commit()
        flash("🗑 設定をすべてリセットしました", "warning")
    except Exception as e:
        conn.rollback()
        print(f"Reset Error: {e}")
    finally:
        conn.close()
    return redirect(url_for('makeshift.settings'))
# ==========================================
# 4.5 需要をリセット（全削除）する処理
# ==========================================
@makeshift_bp.route("/settings/demand/delete", methods=["POST"])
def delete_demand():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        time_slot = request.form.get("time_slot")
        position_id = request.form.get("position_id")
        day_type = request.form.get("day_type", "weekday")  # ★追加
        
        cursor.execute("""
            DELETE FROM shift_demand 
            WHERE time_slot = %s AND position_id = %s AND day_type = %s
        """, (time_slot, position_id, day_type))  # ★day_type追加
        
        conn.commit()
        flash(f"✅ {time_slot} の設定を削除しました", "success")
        
    except Exception as e:
        conn.rollback()
        print(f"Delete Error: {e}")
        flash("削除に失敗しました", "danger")
    finally:
        conn.close()
        
    return redirect(url_for('makeshift.settings'))

# ==========================================
# 4.8曜日タイプ別の需要リセット処理（新規追加）
# ==========================================
@makeshift_bp.route("/settings/demand/reset_by_type", methods=["POST"])
def reset_demand_by_type():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        day_type = request.form.get("day_type", "weekday")
        
        cursor.execute("DELETE FROM shift_demand WHERE day_type = %s", (day_type,))
        conn.commit()
        
        type_label = "平日" if day_type == "weekday" else "土日祝"
        flash(f"🗑 {type_label}の設定をリセットしました", "warning")
        
    except Exception as e:
        conn.rollback()
        print(f"Reset By Type Error: {e}")
        flash("リセットに失敗しました", "danger")
    finally:
        conn.close()
        
    return redirect(url_for('makeshift.settings'))
# ==========================================
# 5. 確定シフト取得API
# ==========================================
@makeshift_bp.route("/api/shifts/all")
def get_all_confirmed_shifts():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT s.user_id, a.name AS user_name, s.date, s.start_time, s.end_time, s.type
        FROM shift_table s
        JOIN account a ON s.user_id = a.ID
        ORDER BY s.date, s.start_time
    """)
    confirmed_shifts = cursor.fetchall()
    cursor.close()
    conn.close()

    formatted_shifts = []
    for shift in confirmed_shifts:
        formatted_shifts.append({
            "user_id": shift["user_id"],
            "user_name": shift["user_name"],
            "date": shift["date"].strftime("%Y-%m-%d"),
            "start_time": format_time(shift["start_time"]),
            "end_time": format_time(shift["end_time"]),
            "type": shift["type"]
        })
    return jsonify({"shifts": formatted_shifts})

@makeshift_bp.route("/api/shifts/user/<int:user_id>")
def get_user_shifts(user_id):
    """ユーザーのシフト情報を取得するAPI"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 1. ユーザー情報を取得
        cursor.execute("SELECT name FROM account WHERE ID = %s", (user_id,))
        user_data = cursor.fetchone()
        
        print(f"🔍 DEBUG: user_id={user_id}, user_data={user_data}")
        
        if not user_data:
            conn.close()
            print(f"❌ ユーザーID {user_id} が見つかりません")
            return jsonify({"error": "User not found"}), 404
        
        # 2. shift_tableから該当ユーザーのシフトを取得
        # ★重要: 負のuser_idは除外
        cursor.execute("""
            SELECT user_id, date, start_time, end_time, type
            FROM shift_table
            WHERE user_id = %s AND user_id > 0
            ORDER BY date, start_time
        """, (user_id,))
        user_shifts = cursor.fetchall()
        
        print(f"📊 DEBUG: 取得したシフト件数={len(user_shifts)}")
        print(f"📋 DEBUG: シフトデータ: {user_shifts}")
        
        # 3. 時刻をフォーマット
        formatted_shifts = []
        for shift in user_shifts:
            formatted_shift = {
                "user_id": shift["user_id"],
                "user_name": user_data["name"],  # ★追加: ユーザー名を含める
                "date": shift["date"].strftime("%Y-%m-%d") if hasattr(shift["date"], 'strftime') else str(shift["date"]),
                "start_time": format_time(shift["start_time"]),
                "end_time": format_time(shift["end_time"]),
                "type": shift["type"]
            }
            formatted_shifts.append(formatted_shift)
            print(f"✅ フォーマット済みシフト: {formatted_shift}")
        
        response = {
            "user_id": user_id,
            "user_name": user_data["name"],
            "shifts": formatted_shifts
        }
        
        print(f"📤 APIレスポンス: {response}")
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        conn.close()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# ★新規追加: デバッグ用エンドポイント
@makeshift_bp.route("/api/debug/shifts_all")
def debug_all_shifts():
    """データベースに保存されている全てのシフトを確認するデバッグAPI"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT s.user_id, a.name as user_name, s.date, s.start_time, s.end_time, s.type
            FROM shift_table s
            LEFT JOIN account a ON s.user_id = a.ID
            ORDER BY s.user_id, s.date, s.start_time
            LIMIT 100
        """)
        all_shifts = cursor.fetchall()
        
        print(f"🔍 DEBUG: DB内の全シフト件数={len(all_shifts)}")
        for shift in all_shifts:
            print(f"  {shift}")
        
        # フォーマット
        formatted = []
        for shift in all_shifts:
            formatted.append({
                "user_id": shift["user_id"],
                "user_name": shift["user_name"],
                "date": shift["date"].strftime("%Y-%m-%d") if hasattr(shift["date"], 'strftime') else str(shift["date"]),
                "start_time": format_time(shift["start_time"]),
                "end_time": format_time(shift["end_time"]),
                "type": shift["type"]
            })
        
        return jsonify({
            "total_count": len(all_shifts),
            "shifts": formatted
        })
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
# === 従業員向けシフト確認画面 ===
@makeshift_bp.route("/user_shift_view/<int:user_id>")
def show_user_shift_view(user_id):
    """
    指定されたユーザーIDのシフトを確認するためのテンプレートを表示するルート。
    この画面のJavaScriptからAPIを呼び出してシフトデータを取得します。
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # ユーザー名を取得
    cursor.execute("SELECT name FROM account WHERE ID = %s", (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if not user_data:
        return "ユーザーが見つかりません。", 404

    # テンプレートをレンダリングし、ユーザーIDとユーザー名を渡す
    return render_template("user_shift_view.html", 
    user_id=user_id, 
    user_name=user_data['name'])


