from flask import Blueprint, render_template, jsonify, request, redirect, url_for
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
    print("🧮 シフト自動作成画面に遷移しました！")
    return redirect(url_for('makeshift.show_admin_shift'))


# === 自動生成ロジック ===
# ... (makeshift_bp.route("/generate") の定義まで省略) ...

# === 自動生成ロジック（希望スコア最大化ロジックを統合） ===
# ... (makeshift_bp.route("/generate") の定義まで省略) ...

# === 自動生成ロジック（希望時刻絶対優先ロジックを統合） ===
# ... (makeshift_bp.route("/generate") の定義まで省略) ...

# === 自動生成ロジック（複合目標関数に修正） ===----------------------------------------------------------------------
from ortools.sat.python import cp_model
from datetime import datetime, time as time_cls, timedelta, date as date_cls
import traceback
from flask import jsonify, render_template

# ⚠️ 注意: 以下のユーティリティ関数は、あなたの環境で定義されている必要があります
# def get_db_connection(): ...
# def ensure_time_obj(time_data): ...
# def to_time_str(time_obj): ...
# def format_time(time_obj): ...

# 'balance'モードの場合に、勤務時間の公平性を評価するためのペナルティ重み
FAIRNESS_PENALTY_WEIGHT = 100
# 'preference'モードの場合に、希望充足度を最大化するための重み
PREFERENCE_REWARD_WEIGHT = 1000  

# 🚨 注意: このコードは、元のファイルで定義されている helper functions (get_db_connection, format_time, ensure_time_obj, to_time_str) が既に存在し、インポートされていることを前提としています。
# from datetime import datetime, time as time_cls, timedelta, date as date_cls
# from ortools.sat.python import cp_model
# import traceback

# ==========================================
# 1. シフト自動生成ロジック (メイン機能)
# ==========================================
# ==========================================
# 1. シフト自動生成ロジック (定員厳守・スリム化版)
# ==========================================
# ==========================================
# 1. シフト自動生成ロジック (時間エラー完全修正版)
# ==========================================
# ==========================================
# 1. シフト自動生成ロジック (修正版)
# ==========================================
@makeshift_bp.route("/auto_calendar")
def auto_calendar():
    # ★修正1: 必要な部品をここで確実にインポート
    from datetime import time, datetime, timedelta 
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 0. 初期データ取得
        cursor.execute("SELECT * FROM shift_settings LIMIT 1")
        row = cursor.fetchone()
        
        if row:
            settings = {
                "start_time": str(row["start_time"])[:5],
                "end_time": str(row["end_time"])[:5],
                "break_minutes": row.get("break_minutes", 60),
                "interval_minutes": row.get("interval_minutes", 15),
                "max_hours_per_day": row.get("max_hours_per_day", 8),
                "min_hours_per_day": row.get("min_hours_per_day", 0),
                "max_people_per_shift": row.get("max_people_per_shift", 30),
                "auto_mode": row.get("auto_mode", "balance")
            }
        else:
            return render_template("auto_calendar.html", message="シフト設定が未登録です。", shifts=[], settings={})

        # =====================================================
        # 🔧 安全な時間変換関数
        # =====================================================
        def safe_to_time(val):
            if val is None: return time(0, 0)
            if isinstance(val, time): return val
            if isinstance(val, timedelta): return (datetime.min + val).time()
            
            s = str(val).strip()
            try:
                return datetime.strptime(s, "%H:%M:%S").time()
            except ValueError:
                try:
                    return datetime.strptime(s, "%H:%M").time()
                except ValueError:
                    parts = s.split(':')
                    if len(parts) >= 2:
                        return time(int(parts[0]), int(parts[1]))
            return time(0, 0)

        SHIFT_START = safe_to_time(settings['start_time'])
        SHIFT_END = safe_to_time(settings['end_time'])
        INTERVAL_MINUTES = int(settings['interval_minutes'])

        settings['start_time'] = SHIFT_START.strftime("%H:%M")
        settings['end_time'] = SHIFT_END.strftime("%H:%M")

        cursor.execute("SELECT ID, name FROM account")
        users_data = cursor.fetchall()
        user_ids = [str(u['ID']) for u in users_data]
        num_users = len(user_ids)
        user_map = {user_id: i for i, user_id in enumerate(user_ids)}
        
        if num_users == 0:
            return render_template("auto_calendar.html", message="登録ユーザーがいません。", shifts=[], settings=settings)
        
        # 1. スキル読み込み
        user_skill_ids = {}
        cursor.execute("SELECT user_id, position_id FROM user_positions")
        for row in cursor.fetchall():
            uid = str(row['user_id'])
            if uid not in user_skill_ids: user_skill_ids[uid] = []
            user_skill_ids[uid].append(row['position_id'])
            
        # 2. 需要読み込み
        demand_map = {}
        cursor.execute("SELECT time_slot, position_id, required_count FROM shift_demand")
        for row in cursor.fetchall():
            t_obj = safe_to_time(row['time_slot'])
            t_str = t_obj.strftime("%H:%M")
            if t_str not in demand_map: demand_map[t_str] = {}
            demand_map[t_str][row['position_id']] = row['required_count']

        # 3. シフト生成ループ
        cursor.execute("SELECT DISTINCT date FROM calendar WHERE work = 1 ORDER BY date")
        target_dates = [row['date'] for row in cursor.fetchall()]

        cursor.execute("DELETE FROM shift_table")
        conn.commit()
        
        if not target_dates:
            conn.close()
            return render_template("auto_calendar.html", message="希望シフトが登録されていません。", shifts=[], settings=settings)

        all_generated_shifts = []

        for target_date_obj in target_dates:
            target_date_str = target_date_obj.strftime("%Y-%m-%d")

            cursor.execute("""
                SELECT ID, date, start_time, end_time, work 
                FROM calendar 
                WHERE date = %s AND work = 1
            """, (target_date_str,))
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
            
            for u_idx in range(num_users):
                for t_idx in range(num_intervals):
                    shifts[u_idx, t_idx] = model.NewBoolVar(f's_{u_idx}_{t_idx}_{target_date_str}')
            
            # ★修正2: demand_fulfillment はループの外で初期化！
            demand_fulfillment = [] 

            # 時間ごとの制約
            for t_idx, t_time in enumerate(time_intervals):
                t_str = t_time.strftime("%H:%M")
                total_required = 0
                
                if t_str in demand_map:
                    current_demand = demand_map[t_str]
                    for needed_pos_id, needed_count in current_demand.items():
                        total_required += needed_count
                        capable_vars = []
                        for u_idx in range(num_users):
                            user_id = user_ids[u_idx]
                            if needed_pos_id in user_skill_ids.get(user_id, []):
                                capable_vars.append(shifts[u_idx, t_idx])
                        if capable_vars:
                            model.Add(sum(capable_vars) <= needed_count)
                            demand_fulfillment.append(sum(capable_vars))
                
                # 定員オーバー禁止
                model.Add(sum(shifts[u_idx, t_idx] for u_idx in range(num_users)) <= total_required)

            # 希望シフト制約
            users_with_preference = {row['ID'] for row in preference_rows}
            for u_idx, u_id in enumerate(user_ids):
                if u_id not in users_with_preference:
                    for t_idx in range(num_intervals):
                        model.Add(shifts[u_idx, t_idx] == 0)

            preference_fulfillment = [] 
            for row in preference_rows:
                u_id = row['ID']
                if u_id not in user_map: continue
                u_idx = user_map[u_id]
                
                st_val = safe_to_time(row['start_time'])
                en_val = safe_to_time(row['end_time'])
                
                for t_idx, t_time in enumerate(time_intervals):
                    if st_val <= t_time < en_val:
                        preference_fulfillment.append(shifts[u_idx, t_idx])
                    else:
                        model.Add(shifts[u_idx, t_idx] == 0)

            # 目的関数
            model.Maximize(sum(demand_fulfillment) * 10 + sum(preference_fulfillment) * 1)

            solver = cp_model.CpSolver()
            status = solver.Solve(model)
            
            if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
                for u_idx in range(num_users):
                    user_id = user_ids[u_idx]
                    current_block_start = None
                    current_role = None
                    
                    for t_idx in range(num_intervals):
                        is_working = solver.Value(shifts[u_idx, t_idx]) == 1
                        
                        if is_working:
                            t_time = time_intervals[t_idx]
                            t_str = t_time.strftime("%H:%M")
                            
                            this_role = "work"
                            if t_str in demand_map:
                                needed = demand_map[t_str]
                                my_skills = user_skill_ids.get(str(user_id), [])
                                for pid in my_skills:
                                    if pid in needed and needed[pid] > 0:
                                        if pid == 1: this_role = "ホール"
                                        elif pid == 2: this_role = "キッチン"
                                        elif pid == 3: this_role = "洗い場"
                                        break
                            
                            if current_block_start is None:
                                current_block_start = t_time
                                current_role = this_role
                            elif this_role != current_role:
                                end_dt_calc = datetime.combine(base_date, t_time)
                                all_generated_shifts.append({
                                    "user_id": user_id, 
                                    "date": target_date_str,
                                    "start_time": current_block_start.strftime("%H:%M"),
                                    "end_time": end_dt_calc.time().strftime("%H:%M"),
                                    "type": current_role
                                })
                                current_block_start = t_time
                                current_role = this_role
                        
                        else:
                            if current_block_start is not None:
                                end_dt_calc = datetime.combine(base_date, time_intervals[t_idx])
                                all_generated_shifts.append({
                                    "user_id": user_id, 
                                    "date": target_date_str,
                                    "start_time": current_block_start.strftime("%H:%M"),
                                    "end_time": end_dt_calc.time().strftime("%H:%M"),
                                    "type": current_role
                                })
                                current_block_start = None
                                current_role = None

                    if current_block_start is not None:
                        last_t = time_intervals[-1]
                        last_end_dt = datetime.combine(base_date, last_t) + timedelta(minutes=INTERVAL_MINUTES)
                        all_generated_shifts.append({
                            "user_id": user_id, 
                            "date": target_date_str,
                            "start_time": current_block_start.strftime("%H:%M"),
                            "end_time": last_end_dt.time().strftime("%H:%M"),
                            "type": current_role
                        })

        if all_generated_shifts:
            sql = "INSERT INTO shift_table (user_id, date, start_time, end_time, type) VALUES (%s, %s, %s, %s, %s)"
            data = [(s['user_id'], s['date'], s['start_time'], s['end_time'], s['type']) for s in all_generated_shifts]
            cursor.executemany(sql, data)
            conn.commit()
            
            cursor.execute("""
                SELECT s.*, a.name as user_name 
                FROM shift_table s 
                LEFT JOIN account a ON s.user_id = a.ID 
                ORDER BY s.user_id, s.date, s.start_time
            """)
            final_shifts = cursor.fetchall()
            
            formatted = []
            for s in final_shifts:
                st = safe_to_time(s['start_time']).strftime("%H:%M")
                en = safe_to_time(s['end_time']).strftime("%H:%M")
                
                formatted.append({
                    "user_id": s['user_id'],
                    "user_name": s['user_name'],
                    "date": str(s['date']),
                    "start_time": st,
                    "end_time": en,
                    "type": s['type']
                })
            
            conn.close()
            return render_template("auto_calendar.html", settings=settings, shifts=formatted, message=f"{len(formatted)}件のシフトを生成しました。")
            
        conn.close()
        return render_template("auto_calendar.html", settings=settings, shifts=[], message="シフトが作成されませんでした。")

    except Exception as e:
        conn.close()
        import traceback
        print(traceback.format_exc())
        return render_template("auto_calendar.html", settings=settings if 'settings' in locals() else {}, shifts=[], message=f"エラーが発生しました: {str(e)}")
#-------------------------------------------------------------------------------------------------------------
# ==========================================
# 2. 設定画面の表示と基本設定の更新
# ==========================================
@makeshift_bp.route("/settings", methods=["GET", "POST"])
def settings():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # --- 1. 現在の基本設定を取得 ---
    cursor.execute("SELECT * FROM shift_settings LIMIT 1")
    settings_data = cursor.fetchone()

    # データがない場合の初期値
    if not settings_data:
        settings_data = {
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

    # --- 2. 役割リストを取得 ---
    cursor.execute("SELECT * FROM positions")
    positions_list = cursor.fetchall()
    
    # --- 3. 現在の需要設定を取得 ---
    cursor.execute("""
        SELECT d.id, d.time_slot, d.required_count, p.name as position_name
        FROM shift_demand d
        LEFT JOIN positions p ON d.position_id = p.id
        ORDER BY d.time_slot, d.position_id
    """)
    raw_demands = cursor.fetchall()
    
    # 時間変換ロジック
    formatted_demands = []
    for r in raw_demands:
        ts = r['time_slot']
        ts_str = ""
        if isinstance(ts, timedelta):
            total_seconds = int(ts.total_seconds())
            h = total_seconds // 3600
            m = (total_seconds % 3600) // 60
            ts_str = f"{h:02d}:{m:02d}"
        else:
            ts_str = str(ts)[:5]
        
        pos_name = r['position_name'] if r['position_name'] else f"Role-{r['position_id']}"
        formatted_demands.append({
            'time_slot': ts_str,
            'position_name': pos_name,
            'required_count': r['required_count']
        })

    # --- 4. POST（更新処理） ---
    if request.method == "POST":
        try:
            start_time = request.form["start_time"]
            end_time = request.form["end_time"]
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
                """, (
                    start_time, end_time, break_minutes, interval_minutes,
                    max_hours_per_day, min_hours_per_day, max_people_per_shift, auto_mode, existing_id["ID"]
                ))
            else:
                cursor.execute("""
                    INSERT INTO shift_settings 
                    (start_time, end_time, break_minutes, interval_minutes, max_hours_per_day, min_hours_per_day, max_people_per_shift, auto_mode, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    start_time, end_time, break_minutes, interval_minutes,
                    max_hours_per_day, min_hours_per_day, max_people_per_shift, auto_mode
                ))
            conn.commit()
        except Exception as e:
            print(f"Error: {e}")
            conn.rollback()
        finally:
            conn.close()
        
        # POSTの後のリダイレクト（インデント注意：ifの中）
        return redirect(url_for("makeshift.settings"))

    # --- 5. GET（表示処理） ---
    conn.close()

    # 時刻フォーマット調整
    for key in ["start_time", "end_time"]:
        if settings_data[key]:
            settings_data[key] = str(settings_data[key])[:5]
        else:
            settings_data[key] = "09:00" if key == "start_time" else "18:00"

    # ★ここが一番大事！このreturnが左端（defと同じ縦ラインの1つ内側）にある必要があります
    return render_template("shift_setting.html", 
                           settings=settings_data, 
                           positions=positions_list, 
                           demands=formatted_demands)
# ==========================================
# 3. 需要（ピークタイム）を追加する処理
# ==========================================
@makeshift_bp.route("/settings/demand/add", methods=["POST"])
def add_demand():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        start_time_str = request.form['start_time']
        end_time_str = request.form['end_time']
        position_id = request.form['position_id']
        count = int(request.form['required_count'])
        
        t_start = datetime.strptime(start_time_str, "%H:%M")
        t_end = datetime.strptime(end_time_str, "%H:%M")
        
        if t_start >= t_end:
            return redirect(url_for('makeshift.settings'))

        current = t_start
        while current < t_end:
            time_slot = current.strftime("%H:%M")
            cursor.execute("DELETE FROM shift_demand WHERE time_slot = %s AND position_id = %s", (time_slot, position_id))
            cursor.execute("INSERT INTO shift_demand (time_slot, position_id, required_count) VALUES (%s, %s, %s)", (time_slot, position_id, count))
            current += timedelta(minutes=15)
            
        conn.commit()
    except Exception as e:
        print(f"Error adding demand: {e}")
        conn.rollback()
    finally:
        conn.close()
        
    return redirect(url_for('makeshift.settings'))


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
    except Exception as e:
        print(f"Error resetting demand: {e}")
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
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT name FROM account WHERE ID = %s", (user_id,))
    user_data = cursor.fetchone()
    if not user_data:
        conn.close()
        return jsonify({"error": "User not found"}), 404
        
    cursor.execute("""
        SELECT date, start_time, end_time, type
        FROM shift_table
        WHERE user_id = %s
        ORDER BY date, start_time
    """, (user_id,))
    user_shifts = cursor.fetchall()
    cursor.close()
    conn.close()

    formatted_shifts = []
    for shift in user_shifts:
        formatted_shifts.append({
            "date": shift["date"].strftime("%Y-%m-%d"),
            "start_time": format_time(shift["start_time"]),
            "end_time": format_time(shift["end_time"]),
            "type": shift["type"]
        })
    return jsonify({
        "user_id": user_id,
        "user_name": user_data["name"],
        "shifts": formatted_shifts
    })

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

# ==========================================
# 🚑 ヘルプ募集機能 (ワンタップ配信システム)
# ==========================================

@makeshift_bp.route("/api/help/create", methods=["POST"])
def create_help_request():
    """
    店長用: ヘルプ募集を作成し、通知対象（空いているスタッフ）をリストアップするAPI
    POSTデータ: { "date": "2025-11-20", "start_time": "17:00", "end_time": "22:00" }
    """
    data = request.json
    target_date = data.get("date")
    start_time_str = data.get("start_time")
    end_time_str = data.get("end_time")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. 募集データをDBに登録
        cursor.execute("""
            INSERT INTO help_requests (date, start_time, end_time, status)
            VALUES (%s, %s, %s, 'open')
        """, (target_date, start_time_str, end_time_str))
        request_id = cursor.lastrowid
        
        # 2. 「その時間にすでにシフトが入っている人」を除外してターゲットを抽出
        # (shift_table に重複する時間帯があるユーザーIDを取得)
        cursor.execute("""
            SELECT DISTINCT user_id 
            FROM shift_table
            WHERE date = %s
            AND NOT (end_time <= %s OR start_time >= %s) 
        """, (target_date, start_time_str, end_time_str))
        busy_users = [row['user_id'] for row in cursor.fetchall()]

        # 全ユーザーから忙しい人を除外
        query = "SELECT ID, name, line_id FROM account" # 👈 ここに line_id が含まれているか確認！

        if busy_users:
            # IDが busy_users に含まれない人を抽出
            format_strings = ','.join(['%s'] * len(busy_users))
            query += f" WHERE ID NOT IN ({format_strings}) AND line_id IS NOT NULL"
            cursor.execute(query, tuple(busy_users))
        else:
            # 🚨 修正が必要な行
            cursor.execute(query + " WHERE line_id IS NOT NULL")
            
        eligible_staff = cursor.fetchall()

        # 🚨 デバッグ用: 抽出されたスタッフのリストをターミナルに出力
        print("--- デバッグ情報: 抽出された対象スタッフ ---")
        print(eligible_staff)
        print("---------------------------------------")
        
        conn.commit()

        # --- ▼▼▼ ここからLINE通知ロジックを追加/変更 ▼▼▼ ---
        
        # 3. ターゲットのスタッフにLINE通知を送信
        target_count = 0
        
        # 応募用URLを生成 (このURLはスタッフが応募ボタンを押した際に遷移するURL)
        # 外部URLを生成するために、_external=True と適切な SERVER_NAME 設定が必要です
        # 例として、ここでは固定のURLを使用します。
        # 実際のFlask環境に合わせて、url_for('makeshift.help_landing_page', request_id=request_id, _external=True) を推奨
        help_url = f"https://your.domain.com/makeshift/help/respond/{request_id}"
        
        request_data = {
            "date": target_date,
            "start_time": start_time_str,
            "end_time": end_time_str,
            "request_id": request_id
        }

        for staff in eligible_staff:
            # LINE ID が設定されているか確認
            if staff.get('line_id'):
                send_help_request_to_staff(
                    staff_line_id=staff['line_id'],
                    request_data=request_data,
                    help_url=help_url,
                    # 🚨 修正: 必要な引数 'staff_name' を追加 🚨
                    staff_name=staff['name'] 
                )
                target_count += 1
        
        # --- ▲▲▲ LINE通知ロジック追加終了 ▲▲▲ ---
        
        conn.commit()

        # 4. Bot送信用にデータを返す (レスポンスを変更)
        return jsonify({
            "message": "募集を作成し、通知を送信しました。",
            "request_id": request_id,
            "target_count": target_count, # 実際に通知が送られた人数を返す
            "details": {
                "date": target_date,
                "time": f"{start_time_str}〜{end_time_str}"
            }
        })

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@makeshift_bp.route("/api/help/accept", methods=["POST"])
def accept_help_request():
    """
    スタッフ用: ヘルプに応募するAPI (早い者勝ちロジック)
    POSTデータ: { "request_id": 1, "user_id": 5 }
    """
    data = request.json
    req_id = data.get("request_id")
    user_id = data.get("user_id")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. トランザクション開始
        conn.start_transaction()

        # 2. 【重要】早い者勝ち判定
        # status='open' の場合のみ更新を行う。更新件数が1なら勝ち、0なら既に埋まった。
        cursor.execute("""
            UPDATE help_requests 
            SET status = 'closed', accepted_by = %s
            WHERE id = %s AND status = 'open'
        """, (user_id, req_id))
        
        if cursor.rowcount == 0:
            # 既に他の誰かが埋めてしまった場合
            conn.rollback()
            return jsonify({"status": "failed", "message": "タッチの差で募集が埋まってしまいました🙇‍♂️"}), 409

        # 3. 募集情報を取得して shift_table に確定シフトとして書き込む
        cursor.execute("SELECT date, start_time, end_time FROM help_requests WHERE id = %s", (req_id,))
        req_data = cursor.fetchone()

        cursor.execute("""
            INSERT INTO shift_table (user_id, date, start_time, end_time, type)
            VALUES (%s, %s, %s, %s, 'help')
        """, (user_id, req_data['date'], req_data['start_time'], req_data['end_time']))

        conn.commit()

        return jsonify({
            "status": "success", 
            "message": "シフトが確定しました！ありがとうございます！"
        })

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

        # makeshift.py (例)

from flask import request, jsonify # ← request と jsonify がインポートされているか確認

# 🚨 User ID 取得のためのデバッグエンドポイント 🚨
# /webhook エンドポイントのコード（makeshift.py または app.py 内）

@makeshift_bp.route("/webhook", methods=["POST"])
def webhook():
    # 🚨 ここが重要です 🚨
    # request.json を print() しているか確認してください
    # print(request.json) 
    
    # さらに、見つけやすくするために、JSON 構造全体を文字列化して出力します
    import json
    # request.json を受け取ります
    data = request.get_json()
    
    print("--- LINE Webhook データ全体 (JSONダンプ) ---")
    # indent=2 で整形し、見やすく出力
    print(json.dumps(data, indent=2))
    print("-----------------------------------------")

    return jsonify({}), 200