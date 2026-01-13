# makeshift.py の1行目を以下に置き換え

from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash, session

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
#---------------------------------------------------------------------------------------------------------------------------------


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
#---------------------------------------------------------------------------------------------------------------------------------

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
#---------------------------------------------------------------------------------------------------------------------------------

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
#---------------------------------------------------------------------------------------------------------------------------------

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
#---------------------------------------------------------------------------------------------------------------------------------


# === 管理者画面 ===
@makeshift_bp.route("/admin")
def show_admin_shift():
    if "user_id" not in session:
        return redirect(url_for("login.login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        user_id = session["user_id"]
        
        # 1. ユーザーの店舗IDを取得
        cursor.execute("SELECT store_id FROM account WHERE ID = %s", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            return "店舗情報が見つかりません", 404
        store_id = user_row["store_id"]

        # 2. 翌月・締め切り・公開状況の計算
        today = datetime.now()
        # 確実に「来月」の情報を出すための計算
        next_month_date = (today.replace(day=28) + timedelta(days=5))
        next_month_val = next_month_date.month
        next_month_year = next_month_date.year
        target_month_str = next_month_date.strftime("%Y-%m")

        # 締め切り日を取得
        cursor.execute("SELECT deadline_day FROM shift_settings WHERE store_id = %s", (store_id,))
        setting = cursor.fetchone()
        deadline_day = setting['deadline_day'] if setting else 20

        # 公開ステータスを取得
        cursor.execute("SELECT is_published FROM shift_publish_status WHERE store_id = %s AND target_month = %s", 
                       (store_id, target_month_str))
        publish_data = cursor.fetchone()
        is_published = publish_data['is_published'] if publish_data else 0

        # 3. 翌月分の希望シフト(calendar)を取得
        cursor.execute("""
            SELECT c.ID, c.date, c.start_time, c.end_time 
            FROM calendar c
            JOIN account a ON c.ID = a.ID
            WHERE a.store_id = %s AND MONTH(c.date) = %s AND YEAR(c.date) = %s
            ORDER BY c.date, c.start_time
        """, (store_id, next_month_val, next_month_year))
        rows = cursor.fetchall()
        
        # 4. 確定済みシフト(shift_table)を取得
        cursor.execute("""
            SELECT s.user_id, s.date, s.start_time, s.end_time, s.type 
            FROM shift_table s
            JOIN account a ON s.user_id = a.ID
            WHERE a.store_id = %s AND MONTH(s.date) = %s AND YEAR(s.date) = %s
            ORDER BY s.date, s.start_time
        """, (store_id, next_month_val, next_month_year))
        confirmed_shifts_raw = cursor.fetchall()

        # 5. 希望シフトの集計 (results の作成)
        if not rows:
            results = []
        else:
            days = sorted(set(r["date"].strftime("%Y-%m-%d") for r in rows))
            results = []
            for d in days:
                registered = [
                    (format_time(r["start_time"]), format_time(r["end_time"]))
                    for r in rows
                    if r["date"].strftime("%Y-%m-%d") == d and r["start_time"] and r["end_time"]
                ]
                # 空き時間の計算
                free_slots = find_free_times(registered)
                results.append({"date": d, "registered": registered, "free_slots": free_slots})

        # 6. 確定シフトのフォーマット
        formatted_confirmed = []
        for shift in confirmed_shifts_raw:
            formatted_confirmed.append({
                "date": shift["date"].strftime("%Y-%m-%d"),
                "user_id": shift["user_id"],
                "start_time": format_time(shift["start_time"]),
                "end_time": format_time(shift["end_time"]),
                "type": shift["type"]
            })

        return render_template("admin.html", 
                               results=results, 
                               confirmed_shifts=formatted_confirmed,
                               next_month=next_month_val,
                               deadline_day=deadline_day,
                               is_published=is_published,
                               is_application_open=(today.day <= deadline_day))
                               
    except Exception as e:
        print(f"Admin View Error: {e}")
        import traceback
        traceback.print_exc()
        return "システムエラーが発生しました", 500
    finally:
        cursor.close()
        conn.close()
#---------------------------------------------------------------------------------------------------------------------------------


@makeshift_bp.route("/day/<date_str>")
def get_day_details(date_str):
    from flask import session
    
    # ★追加: ログインチェック
    if "user_id" not in session:
        return jsonify({"error": "未ログイン"}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # ★追加: ログインユーザーの店舗IDを取得
        user_id = session["user_id"]
        print(f"🔍 DEBUG: user_id = {user_id}, type = {type(user_id)}")  # デバッグ用
        
        cursor.execute("SELECT store_id FROM account WHERE ID = %s", (user_id,))
        store_result = cursor.fetchone()
        
        print(f"🔍 DEBUG: store_result = {store_result}")  # デバッグ用
        
        if not store_result or not store_result.get('store_id'):
            cursor.close()
            conn.close()
            return jsonify({"error": "店舗情報が見つかりません"}), 404
        
        store_id = store_result['store_id']
        print(f"🔍 DEBUG: store_id = {store_id}")  # デバッグ用
        
        # ★修正: 同じ店舗のユーザーのみ取得
        cursor.execute("""
            SELECT c.ID, c.date, c.start_time, c.end_time
            FROM calendar c
            JOIN account a ON c.ID = a.ID
            WHERE c.date = %s AND a.store_id = %s
            ORDER BY c.start_time
        """, (date_str, store_id))
        rows = cursor.fetchall()
        
        print(f"🔍 DEBUG: rows count = {len(rows)}")  # デバッグ用
        
    except Exception as e:
        print(f"❌ ERROR: {e}")  # デバッグ用
        import traceback
        traceback.print_exc()
        cursor.close()
        conn.close()
        return jsonify({"error": str(e)}), 500
    
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
#---------------------------------------------------------------------------------------------------------------------------------


# === シフト遷移 ===
@makeshift_bp.route("/generate")
def generate_shift():
    return redirect(url_for('makeshift.show_admin_shift'))

#---------------------------------------------------------------------------------------------------------------------------------

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
# 1. シフト自動生成ロジック (メイン機能)---------------------------------------------------------------------------------------------------------------------------------
# ==========================================
# makeshift.py の auto_calendar 関数をこれに置き換えてください

@makeshift_bp.route("/auto_calendar")
def auto_calendar():
    from datetime import time, datetime, timedelta 
    from ortools.sat.python import cp_model
    import traceback

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # ========================================================
        # 1. ヘルパー関数定義
        # ========================================================
        def safe_time_format(val):
            if val is None: return "00:00"
            if hasattr(val, 'strftime'): return val.strftime("%H:%M")
            if hasattr(val, 'total_seconds'):
                total_seconds = int(val.total_seconds())
                h, m = divmod(total_seconds, 3600)
                return f"{h:02d}:{m:02d}"
            s = str(val)
            return s[:5] if ':' in s else "00:00"

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

        # ========================================================
        # target_month パラメータの取得
        # ========================================================
        target_month = request.args.get('target_month', type=int)
        
        if not target_month:
            today = datetime.now()
            if today.month == 12:
                target_month = 1
                target_year = today.year + 1
            else:
                target_month = today.month + 1
                target_year = today.year
        else:
            today = datetime.now()
            if target_month < today.month:
                target_year = today.year + 1
            else:
                target_year = today.year

        # ========================================================
        # 2. 設定取得
        # ========================================================
        cursor.execute("SELECT * FROM shift_settings LIMIT 1")
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return render_template("auto_calendar.html", 
                                   settings={}, 
                                   shifts=[], 
                                   message="⚠️ エラー: 管理者設定が行われていません。")

        settings = {
            "start_time": safe_time_format(row["start_time"]),
            "end_time": safe_time_format(row["end_time"]),
            "break_minutes": row.get("break_minutes", 60),
            "interval_minutes": row.get("interval_minutes", 15),
            "max_hours_per_day": row.get("max_hours_per_day", 8),
            "min_hours_per_day": row.get("min_hours_per_day", 0),
            "max_people_per_shift": row.get("max_people_per_shift", 30),
            "auto_mode": row.get("auto_mode", "balance")
        }

        SHIFT_START = safe_to_time(settings['start_time'])
        SHIFT_END = safe_to_time(settings['end_time'])
        INTERVAL_MINUTES = int(settings['interval_minutes'])
        settings['start_time'] = SHIFT_START.strftime("%H:%M")
        settings['end_time'] = SHIFT_END.strftime("%H:%M")

        # ========================================================
        # 3. ユーザー情報の取得
        # ========================================================
        cursor.execute("SELECT ID, name FROM account")
        users_data = cursor.fetchall()
        user_ids = [str(u['ID']) for u in users_data]
        num_users = len(user_ids)
        user_map = {str(user_id): i for i, user_id in enumerate(user_ids)}
        
        position_names = {}
        cursor.execute("SELECT id, name FROM positions")
        for p in cursor.fetchall(): 
            position_names[str(p['id'])] = p['name']

        user_skill_ids = {}
        cursor.execute("SELECT user_id, position_id FROM user_positions")
        for row in cursor.fetchall():
            uid = str(row['user_id'])
            pid = str(row['position_id'])
            if uid not in user_skill_ids: 
                user_skill_ids[uid] = []
            user_skill_ids[uid].append(pid)

        demand_weekday = {}
        demand_weekend = {}
        cursor.execute("SELECT time_slot, position_id, required_count, day_type FROM shift_demand")
        for row in cursor.fetchall():
            t_str = safe_to_time(row['time_slot']).strftime("%H:%M")
            pid = str(row['position_id'])
            day_type = row.get('day_type', 'weekday')
            target_map = demand_weekend if day_type == 'holiday' else demand_weekday
            if t_str not in target_map: 
                target_map[t_str] = {}
            target_map[t_str][pid] = row['required_count']
        
        print(f"DEBUG: 平日需要データ数: {len(demand_weekday)}, 休日需要データ数: {len(demand_weekend)}")

        # ========================================================
        # 4. 対象月のデータ取得
        # ========================================================
        mode = request.args.get('mode', 'fill')
        
        cursor.execute("""
            SELECT DISTINCT date 
            FROM calendar 
            WHERE work = 1 
            AND YEAR(date) = %s 
            AND MONTH(date) = %s 
            ORDER BY date
        """, (target_year, target_month))
        target_dates = [row['date'] for row in cursor.fetchall()]

        if not target_dates:
            conn.close()
            return render_template("auto_calendar.html", 
                                   message=f"{target_month}月の希望シフトが登録されていません", 
                                   shifts=[], 
                                   settings=settings)

        dates_list = [str(d) for d in target_dates]
        placeholders = ','.join(['%s'] * len(dates_list))

        # ========================================================
        # 5. 削除処理
        # ========================================================
        if mode == 'reset':
            sql = f"DELETE FROM shift_table WHERE date IN ({placeholders})"
            cursor.execute(sql, tuple(dates_list))
            print(f"DEBUG: 完全リセット - 削除件数: {cursor.rowcount}")
        elif mode == 'unlock_all':
            sql = f"UPDATE shift_table SET is_locked = 0 WHERE date IN ({placeholders}) AND CAST(user_id AS SIGNED) > 0"
            cursor.execute(sql, tuple(dates_list))
            print(f"DEBUG: 全保護解除 - 更新件数: {cursor.rowcount}")
        else:
            sql = f"""
                DELETE FROM shift_table 
                WHERE date IN ({placeholders})
                AND (
                    (CAST(user_id AS SIGNED) > 0 AND is_locked = 0)
                    OR CAST(user_id AS SIGNED) < 0
                )
            """
            cursor.execute(sql, tuple(dates_list))
            print(f"DEBUG: 通常削除 - 削除件数: {cursor.rowcount}")
        
        conn.commit()
        
        if mode == 'unlock_all':
            cursor.execute(f"""
                SELECT s.user_id, a.name as user_name, s.date, s.start_time, s.end_time, s.type, s.is_locked
                FROM shift_table s 
                LEFT JOIN account a ON s.user_id = a.ID 
                WHERE s.date IN ({placeholders})
                ORDER BY s.user_id, s.date, s.start_time
            """, tuple(dates_list))
            raw_shifts = cursor.fetchall()
            
            final_display_shifts = []
            if raw_shifts:
                for shift in raw_shifts:
                    shift['start_time'] = safe_to_time(shift['start_time']).strftime("%H:%M")
                    shift['end_time'] = safe_to_time(shift['end_time']).strftime("%H:%M")
                    shift['date'] = str(shift['date'])
                    shift['is_locked'] = 0
                    if int(shift['user_id']) < 0: 
                        shift['user_name'] = shift['type']
                    final_display_shifts.append(shift)
            
            conn.close()
            return render_template("auto_calendar.html", 
                                   settings=settings, 
                                   shifts=final_display_shifts, 
                                   message="🔓 全てのシフトの保護を解除しました")
        
        all_generated_shifts = []
        dates_with_shortage = set()

        # ========================================================
        # 6. 日付ごとの最適化ループ
        # ========================================================
        for target_date_obj in target_dates:
            target_date_str = target_date_obj.strftime("%Y-%m-%d")
            
            is_weekend = target_date_obj.weekday() >= 5
            demand_map = demand_weekend if is_weekend else demand_weekday
            
            day_type_str = "休日" if is_weekend else "平日"
            total_demand = sum(sum(d.values()) for d in demand_map.values())
            print(f"DEBUG: {target_date_str}({day_type_str}) - 需要時間帯数: {len(demand_map)}, 総需要: {total_demand}")
            
            time_intervals = []
            base_date = datetime(2000, 1, 1)
            current_dt = base_date.replace(hour=SHIFT_START.hour, minute=SHIFT_START.minute)
            target_end_dt = base_date.replace(hour=SHIFT_END.hour, minute=SHIFT_END.minute)
            
            while current_dt < target_end_dt:
                time_intervals.append(current_dt.time())
                current_dt += timedelta(minutes=INTERVAL_MINUTES)
            
            num_intervals = len(time_intervals)
            if num_intervals == 0: 
                continue

            cursor.execute("""
                SELECT user_id, start_time, end_time, type 
                FROM shift_table 
                WHERE date = %s AND is_locked = 1 AND CAST(user_id AS SIGNED) > 0
            """, (target_date_str,))
            locked_shifts_data = cursor.fetchall()
            
            locked_user_ids_set = set()
            for ls in locked_shifts_data:
                locked_user_ids_set.add(str(ls['user_id']))

            model = cp_model.CpModel()
            shifts = {}
            for u in range(num_users):
                for t in range(num_intervals):
                    shifts[u, t] = model.NewBoolVar(f's_{u}_{t}')

            # --- 修正後 ---
            # 1. まず全ユーザーの「ロックされるべき枠」を整理する
            user_locked_map = {u_idx: [False] * num_intervals for u_idx in range(num_users)}

            for ls in locked_shifts_data:
                uid_str = str(ls['user_id'])
                if uid_str not in user_map: continue
                u_idx = user_map[uid_str]
                l_start = safe_to_time(ls['start_time'])
                l_end = safe_to_time(ls['end_time'])
                
                for t_idx, t_time in enumerate(time_intervals):
                    if l_start <= t_time < l_end:
                        user_locked_map[u_idx][t_idx] = True

            # 2. まとめて制約をかける
            for u_idx, locked_slots in user_locked_map.items():
                # そのユーザーに1つでもロックがある場合のみ処理
                if any(locked_slots):
                    for t_idx, is_locked in enumerate(locked_slots):
                        if is_locked:
                            model.Add(shifts[u_idx, t_idx] == 1)
                        else:
                            model.Add(shifts[u_idx, t_idx] == 0)

            demand_fulfillment = []
            over_staff_penalty = []

            for t_idx, t_time in enumerate(time_intervals):
                t_str = t_time.strftime("%H:%M")
                
                if t_str in demand_map:
                    current_demand = demand_map[t_str]
                    
                    for pid, count in current_demand.items():
                        capable = [shifts[u, t_idx] for u in range(num_users) 
                                   if pid in user_skill_ids.get(user_ids[u], [])]
                        
                        if capable:
                            actual_count = sum(capable)
                            model.Add(actual_count <= count)
                            
                            capped_count = model.NewIntVar(0, count, f'capped_{t_str}_{pid}')
                            model.Add(capped_count <= actual_count)
                            model.Add(capped_count <= count)
                            demand_fulfillment.append(capped_count)

                            excess_count = model.NewIntVar(0, 2, f'excess_{t_str}_{pid}')
                            model.Add(excess_count == actual_count - capped_count)
                            over_staff_penalty.append(excess_count)

                total_req = sum(demand_map[t_str].values()) if t_str in demand_map else 0
                current_total_shifts = sum(shifts[u, t_idx] for u in range(num_users))
                
                if total_req == 0:
                    model.Add(current_total_shifts == 0)
                else:
                    model.Add(current_total_shifts <= total_req)

            max_hours = float(settings['max_hours_per_day'])
            max_intervals = int((max_hours * 60) / INTERVAL_MINUTES)
            min_hours = float(settings.get('min_hours_per_day', 0))
            min_slots = int((min_hours * 60) / INTERVAL_MINUTES)

            user_total_hours = []
            for u in range(num_users):
                total_worked = sum(shifts[u, t] for t in range(num_intervals))
                user_total_hours.append(total_worked)
                
                model.Add(total_worked <= max_intervals)
                
                if min_slots > 0:
                    is_working = model.NewBoolVar(f'is_working_{u}')
                    model.Add(total_worked >= min_slots).OnlyEnforceIf(is_working)
                    model.Add(total_worked == 0).OnlyEnforceIf(is_working.Not())

            max_hours_var = model.NewIntVar(0, max_intervals, 'max_hours')
            min_hours_var = model.NewIntVar(0, max_intervals, 'min_hours')

            for total in user_total_hours:
                model.Add(max_hours_var >= total)
                is_working_user = model.NewBoolVar(f'is_working_check')
                model.Add(total > 0).OnlyEnforceIf(is_working_user)
                model.Add(total == 0).OnlyEnforceIf(is_working_user.Not())
                model.Add(min_hours_var <= total).OnlyEnforceIf(is_working_user)

            balance_penalty = max_hours_var - min_hours_var

            for u in range(num_users):
                start_flags = []
                s0 = model.NewBoolVar(f'start_{u}_0')
                model.Add(s0 == shifts[u, 0])
                start_flags.append(s0)
                
                for t in range(1, num_intervals):
                    st = model.NewBoolVar(f'start_{u}_{t}')
                    model.AddBoolAnd([shifts[u, t], shifts[u, t-1].Not()]).OnlyEnforceIf(st)
                    model.AddBoolOr([shifts[u, t].Not(), shifts[u, t-1]]).OnlyEnforceIf(st.Not())
                    start_flags.append(st)
                
                # ★★★ ここを以下のように書き換え ★★★
                if str(user_ids[u]) in locked_user_ids_set:
                    # ロックされている人は2つ以上の役割（分断勤務）を許可する
                    model.Add(sum(start_flags) <= 2) 
                else:
                    # 通常の人は今まで通り1つの塊（連続勤務）のみ
                    model.Add(sum(start_flags) <= 1)

            cursor.execute("""
                SELECT ID, start_time, end_time 
                FROM calendar 
                WHERE date = %s AND work = 1
            """, (target_date_str,))
            preference_rows = cursor.fetchall()
            
            print(f"DEBUG: {target_date_str} - 希望シフト登録者数: {len(preference_rows)}")
            for row in preference_rows:
                uid = str(row['ID'])
                s_time = safe_to_time(row['start_time']).strftime("%H:%M")
                e_time = safe_to_time(row['end_time']).strftime("%H:%M")
                skills = user_skill_ids.get(uid, [])
                skill_names = [position_names.get(pid, pid) for pid in skills]
                print(f"  - User {uid}: {s_time}~{e_time}, スキル: {skill_names}")

            print(f"DEBUG: {target_date_str} - 需要データ:")
            for t_str, demands in demand_map.items():
                demand_str = ", ".join([f"{position_names.get(pid, pid)}:{cnt}" for pid, cnt in demands.items()])
                print(f"  - {t_str}: {demand_str}")
            
            users_with_pref = {str(row['ID']) for row in preference_rows}
            for u, uid in enumerate(user_ids):
                if str(uid) not in locked_user_ids_set and str(uid) not in users_with_pref:
                    for t in range(num_intervals): 
                        model.Add(shifts[u, t] == 0)

            pref_score = []
            out_of_pref_penalty = []
            
            for row in preference_rows:
                uid_str = str(row['ID'])
                if uid_str not in user_map: 
                    continue
                u = user_map[uid_str]
                
                if uid_str in locked_user_ids_set:
                    continue
                
                s_val = safe_to_time(row['start_time'])
                e_val = safe_to_time(row['end_time'])
                
                for t, t_val in enumerate(time_intervals):
                    if s_val <= t_val < e_val:
                        pref_score.append(shifts[u, t])
                    else:
                        out_of_pref_penalty.append(shifts[u, t])

            recent_work_penalty = []
            cursor.execute("""
                SELECT user_id, COUNT(DISTINCT date) as work_days
                FROM shift_table
                WHERE date BETWEEN %s AND %s AND CAST(user_id AS SIGNED) > 0
                GROUP BY user_id
            """, (target_date_obj - timedelta(days=6), target_date_obj - timedelta(days=1)))
            
            recent_work_days = {str(row['user_id']): row['work_days'] for row in cursor.fetchall()}
            
            for u_idx, user_id in enumerate(user_ids):
                if recent_work_days.get(user_id, 0) >= 5:
                    penalty = sum(shifts[u_idx, t] for t in range(num_intervals))
                    recent_work_penalty.append(penalty)

            WEIGHT_DEMAND = 100
            WEIGHT_PREFERENCE = 10
            WEIGHT_OVERSTAFF = 15
            WEIGHT_BALANCE = -3
            WEIGHT_RECENT_WORK = -2
            WEIGHT_OUT_OF_PREF = -5

            model.Maximize(
                sum(demand_fulfillment) * WEIGHT_DEMAND + 
                sum(pref_score) * WEIGHT_PREFERENCE - 
                sum(over_staff_penalty) * WEIGHT_OVERSTAFF -
                balance_penalty * WEIGHT_BALANCE -
                sum(recent_work_penalty) * WEIGHT_RECENT_WORK -
                sum(out_of_pref_penalty) * WEIGHT_OUT_OF_PREF
            )

            solver = cp_model.CpSolver()
            solver.parameters.num_search_workers = 1
            solver.parameters.random_seed = 42
            solver.parameters.max_time_in_seconds = 30.0
            
            status = solver.Solve(model)
            
            status_names = {
                cp_model.OPTIMAL: "OPTIMAL",
                cp_model.FEASIBLE: "FEASIBLE",
                cp_model.INFEASIBLE: "INFEASIBLE",
                cp_model.MODEL_INVALID: "MODEL_INVALID",
                cp_model.UNKNOWN: "UNKNOWN"
            }
            print(f"DEBUG: {target_date_str} - 最適化結果: {status_names.get(status, 'UNKNOWN')}")

            if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                user_assigned_roles = {}
                active_shortages = {}
                shortage_list_day = []

                for t_idx, t_time in enumerate(time_intervals):
                    t_str = t_time.strftime("%H:%M")
                    
                    # ロックされたユーザーも含めて計算
                    working_users = []
                    locked_users_in_this_slot = []
                    
                    for u_idx in range(num_users):
                        if solver.Value(shifts[u_idx, t_idx]) == 1:
                            user_id = user_ids[u_idx]
                            if user_id in locked_user_ids_set:
                                locked_users_in_this_slot.append(u_idx)
                            else:
                                working_users.append(u_idx)
                    
                    open_slots = []
                    if t_str in demand_map:
                        for pid, count in demand_map[t_str].items():
                            for _ in range(count): 
                                open_slots.append(pid)
                    
                    # ロックユーザーが満たしている需要を先に除外
                    for u_idx in locked_users_in_this_slot:
                        uid = user_ids[u_idx]
                        skills = user_skill_ids.get(uid, [])
                        
                        for skill in skills:
                            if skill in open_slots:
                                open_slots.remove(skill)
                                break
                    
                    # 残りのopen_slotsに対してロックされていないユーザーを割り当て
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
                        if u_idx not in user_assigned_roles: 
                            user_assigned_roles[u_idx] = {}
                        user_assigned_roles[u_idx][t_idx] = role_name

                    # ★★★ 不足データの連結処理 ★★★
                    # 現在の時間帯で不足している役割をカウント
                    current_shortages = {}
                    for pid in open_slots:
                        current_shortages[pid] = current_shortages.get(pid, 0) + 1
                    
                    next_end_dt = datetime.combine(base_date, t_time) + timedelta(minutes=INTERVAL_MINUTES)
                    
                    # 既存の不足データを更新または終了
                    finished_keys = []
                    for key in list(active_shortages.keys()):
                        shortage_data = active_shortages[key]
                        
                        # キーが文字列の場合とタプルの場合の両方に対応
                        if isinstance(key, str):
                            pid = key.split('_')[0]
                        else:
                            pid = str(key[0])
                        
                        if pid in current_shortages and current_shortages[pid] > 0:
                            # まだ不足が続いている → 終了時刻を延長
                            shortage_data['end_time'] = next_end_dt.time().strftime("%H:%M")
                            current_shortages[pid] -= 1
                        else:
                            # 不足が解消された → このブロックを確定
                            finished_keys.append(key)
                    
                    # 確定した不足データをリストに追加
                    for key in finished_keys:
                        shortage_list_day.append(active_shortages[key])
                        del active_shortages[key]
                    
                    # 新しく発生した不足を追加
                    shortage_counter = {}
                    for pid, count in current_shortages.items():
                        for i in range(count):
                            # ユニークなキーを生成（同じ役割の複数不足を区別）
                            shortage_num = shortage_counter.get(pid, 0)
                            shortage_counter[pid] = shortage_num + 1
                            
                            unique_key = f"{pid}_{shortage_num}"
                            
                            p_name = position_names.get(pid, "役割")
                            neg_id = -1 * (int(pid) * 1000 + shortage_num)
                            unique_name = f"🚨 {p_name}不足 ({shortage_num + 1})"
                            
                            active_shortages[unique_key] = {
                                "user_id": neg_id, 
                                "user_name": unique_name,
                                "date": target_date_str,
                                "start_time": t_time.strftime("%H:%M"),
                                "end_time": next_end_dt.time().strftime("%H:%M"), 
                                "type": unique_name
                            }

                # ループ終了後、残っている不足データをすべて追加
                for item in active_shortages.values(): 
                    shortage_list_day.append(item)
                
                print(f"DEBUG: {target_date_str} - 不足データ生成数: {len(shortage_list_day)}")
                
                if shortage_list_day:
                    dates_with_shortage.add(target_date_str)
                
                all_generated_shifts.extend(shortage_list_day)

                for u_idx, roles_map in user_assigned_roles.items():
                    user_id = user_ids[u_idx]
                    
                    if user_id in locked_user_ids_set:
                        continue
                        
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
                                end_dt = datetime.combine(base_date, t_time)
                                all_generated_shifts.append({
                                    "user_id": user_id, 
                                    "date": target_date_str,
                                    "start_time": current_block_start.strftime("%H:%M"),
                                    "end_time": end_dt.time().strftime("%H:%M"), 
                                    "type": current_role
                                })
                                current_block_start = t_time
                                current_role = role_name
                        else:
                            if current_block_start is not None:
                                end_dt = datetime.combine(base_date, time_intervals[t_idx])
                                all_generated_shifts.append({
                                    "user_id": user_id, 
                                    "date": target_date_str,
                                    "start_time": current_block_start.strftime("%H:%M"),
                                    "end_time": end_dt.time().strftime("%H:%M"), 
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
            else:
                print(f"WARNING: {target_date_str} - 最適化失敗。全時間帯を不足として記録します。")
                
                active_shortages = {}
                shortage_list_day = []
                
                for t_idx, t_time in enumerate(time_intervals):
                    t_str = t_time.strftime("%H:%M")
                    
                    if t_str not in demand_map:
                        continue
                    
                    locked_count_by_position = {}
                    for ls in locked_shifts_data:
                        l_start = safe_to_time(ls['start_time'])
                        l_end = safe_to_time(ls['end_time'])
                        if l_start <= t_time < l_end:
                            uid = str(ls['user_id'])
                            if uid in user_skill_ids:
                                for pid in user_skill_ids[uid]:
                                    locked_count_by_position[pid] = locked_count_by_position.get(pid, 0) + 1
                    
                    for pid, required_count in demand_map[t_str].items():
                        locked = locked_count_by_position.get(pid, 0)
                        shortage = max(0, required_count - locked)
                        
                        for i in range(shortage):
                            key = (pid, i, t_idx)
                            next_end_dt = datetime.combine(base_date, t_time) + timedelta(minutes=INTERVAL_MINUTES)
                            
                            if key in active_shortages:
                                active_shortages[key]['end_time'] = next_end_dt.time().strftime("%H:%M")
                            else:
                                p_name = position_names.get(pid, "役割")
                                neg_id = -1 * (int(pid) * 1000 + i)
                                unique_name = f"🚨 {p_name}不足 ({i+1})"
                                active_shortages[key] = {
                                    "user_id": neg_id,
                                    "user_name": unique_name,
                                    "date": target_date_str,
                                    "start_time": t_time.strftime("%H:%M"),
                                    "end_time": next_end_dt.time().strftime("%H:%M"),
                                    "type": unique_name
                                }
                
                for item in active_shortages.values():
                    shortage_list_day.append(item)
                
                print(f"DEBUG: {target_date_str} - 不足データ生成数(失敗時): {len(shortage_list_day)}")
                
                if shortage_list_day:
                    dates_with_shortage.add(target_date_str)
                
                all_generated_shifts.extend(shortage_list_day)


                # 最適化結果の直後（status_namesの出力の後）に追加
                print(f"DEBUG: {target_date_str} - 最適化結果: {status_names.get(status, 'UNKNOWN')}")

                # ★★★ ここに追加 ★★★
                if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                    print(f"DEBUG: {target_date_str} - 配置されたユーザー数:")
                    for u_idx in range(num_users):
                        total_slots = sum(solver.Value(shifts[u_idx, t]) for t in range(num_intervals))
                        if total_slots > 0:
                            user_id = user_ids[u_idx]
                            is_locked = "🔒" if user_id in locked_user_ids_set else ""
                            print(f"  - User {user_id}{is_locked}: {total_slots}スロット ({total_slots * INTERVAL_MINUTES / 60:.1f}時間)")

        # ========================================================
        # 7. DB保存
        # ========================================================
        if all_generated_shifts:
            sql = "INSERT INTO shift_table (user_id, date, start_time, end_time, type, is_locked) VALUES (%s, %s, %s, %s, %s, %s)"
            data = [(s['user_id'], s['date'], s['start_time'], s['end_time'], s['type'], 0) 
                    for s in all_generated_shifts]
            cursor.executemany(sql, data)
            conn.commit()
            print(f"DEBUG: 新規シフト保存 - 件数: {len(data)}, 不足: {len([d for d in data if int(d[0]) < 0])}")
            
        # ========================================================
        # 8. 表示用データ取得
        # ========================================================
        cursor.execute(f"""
            SELECT 
                s.user_id, 
                CASE 
                    WHEN CAST(s.user_id AS SIGNED) < 0 THEN s.type
                    ELSE a.name 
                END as user_name,
                s.date, 
                s.start_time, 
                s.end_time, 
                s.type, 
                s.is_locked
            FROM shift_table s 
            LEFT JOIN account a ON s.user_id = a.ID 
            WHERE s.date IN ({placeholders})
            ORDER BY 
                CASE WHEN CAST(s.user_id AS SIGNED) > 0 THEN 0 ELSE 1 END,
                s.user_id, 
                s.date, 
                s.start_time
        """, tuple(dates_list))
        raw_shifts = cursor.fetchall()
        
        shortage_count_debug = len([s for s in raw_shifts if int(s['user_id']) < 0])
        print(f"DEBUG: 取得した全シフト数: {len(raw_shifts)}, 不足データ数: {shortage_count_debug}")
        
        final_display_shifts = []
        if raw_shifts:
            curr = raw_shifts[0].copy()
            curr['start_time'] = safe_to_time(curr['start_time']).strftime("%H:%M")
            curr['end_time'] = safe_to_time(curr['end_time']).strftime("%H:%M")
            curr['date'] = str(curr['date'])
            curr['is_locked'] = curr.get('is_locked', 0)
            
            if int(curr['user_id']) < 0: 
                curr['user_name'] = curr['type']

            for i in range(1, len(raw_shifts)):
                nxt = raw_shifts[i].copy()
                nxt['start_time'] = safe_to_time(nxt['start_time']).strftime("%H:%M")
                nxt['end_time'] = safe_to_time(nxt['end_time']).strftime("%H:%M")
                nxt['date'] = str(nxt['date'])
                nxt['is_locked'] = nxt.get('is_locked', 0)
                
                if int(nxt['user_id']) < 0: 
                    nxt['user_name'] = nxt['type']

                should_merge = (
                    int(curr['user_id']) > 0 and
                    curr['user_id'] == nxt['user_id'] and 
                    curr['date'] == nxt['date'] and 
                    curr['type'] == nxt['type'] and 
                    curr.get('is_locked') == nxt.get('is_locked') and
                    curr['end_time'] == nxt['start_time']
                )
                
                if should_merge:
                    curr['end_time'] = nxt['end_time']
                else:
                    final_display_shifts.append(curr)
                    curr = nxt
            
            final_display_shifts.append(curr)
        
        final_shortage_count = len([s for s in final_display_shifts if int(s['user_id']) < 0])
        print(f"DEBUG: 最終表示シフト数: {len(final_display_shifts)}, 不足データ数: {final_shortage_count}")

        conn.close()
        
        total_shifts = len([s for s in final_display_shifts if int(s['user_id']) > 0])
        locked_shifts = len([s for s in final_display_shifts if int(s['user_id']) > 0 and s.get('is_locked') == 1])
        shortage_count = len([s for s in final_display_shifts if int(s['user_id']) < 0])
        
        message = f"✅ {target_month}月シフト作成完了: {total_shifts}件 | 🔒保護済み: {locked_shifts}件 | 🚨不足: {shortage_count}件"
        
        return render_template("auto_calendar.html", 
                               settings=settings, 
                               shifts=final_display_shifts, 
                               message=message)

    except Exception as e:
        conn.close()
        print(traceback.format_exc())
        error_settings = settings if 'settings' in locals() else {}
        return render_template("auto_calendar.html", 
                               settings=error_settings, 
                               shifts=[], 
                               message=f"❌ エラーが発生しました: {str(e)}")


@makeshift_bp.route("/toggle_lock", methods=["POST"])
def toggle_lock():
    data = request.json
    shift_user_id = data.get('user_id')
    shift_date = data.get('date')
    shift_start_time = data.get('start_time')
    shift_end_time = data.get('end_time')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        if int(shift_user_id) < 0:
            return jsonify({'status': 'error', 'message': '不足データはロックできません'}), 400
        
        cursor.execute("""
            SELECT is_locked FROM shift_table 
            WHERE user_id = %s AND date = %s AND start_time = %s AND end_time = %s
            LIMIT 1
        """, (shift_user_id, shift_date, shift_start_time, shift_end_time))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({'status': 'error', 'message': 'シフトが見つかりません'}), 404
            
        new_status = 0 if row['is_locked'] else 1
        
        cursor.execute("""
            UPDATE shift_table 
            SET is_locked = %s 
            WHERE user_id = %s AND date = %s AND start_time = %s AND end_time = %s
        """, (new_status, shift_user_id, shift_date, shift_start_time, shift_end_time))
        conn.commit()
        
        print(f"DEBUG toggle_lock: user_id={shift_user_id}, date={shift_date}, time={shift_start_time}-{shift_end_time}, affected_rows={cursor.rowcount}")
        
        return jsonify({'status': 'success', 'new_state': new_status})
        
    except Exception as e:
        print(f"ERROR in toggle_lock: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()
#------------------------------------------------------------------------------------------------------------------------------------------------------
@makeshift_bp.route('/lock_schedule', methods=['POST'])
def lock_schedule():
    # セッションから管理者の店舗IDを取得
    store_id = session.get('store_id') 
    month = request.form.get('month')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # ★ store_id も含めて保存する
    sql = """
        INSERT INTO shift_config (store_id, target_month, deadline_date, is_locked)
        VALUES (%s, %s, CURDATE(), TRUE)
        ON DUPLICATE KEY UPDATE is_locked = TRUE
    """
    cursor.execute(sql, (store_id, month)) # ここで store_id を渡す
    conn.commit()
    
    return redirect(url_for('makeshift_bp.show_admin_shift'))
#------------------------------------------------------------------------------------------------------------------------------------------------------


# ==========================================
# 2. 設定画面の表示と基本設定の更新-----------------------------------------------------------------------------------------
# ==========================================
@makeshift_bp.route("/settings", methods=["GET", "POST"])
def settings():
    # 1. ログイン確認
    if "user_id" not in session:
        flash("ログインが必要です", "danger")
        return redirect(url_for("login.login"))
    
    user_id = session["user_id"]
    
    # DB接続
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # ==========================================================
        # ★ 修正: テーブル名を 'account' に変更しました
        # ==========================================================
        cursor.execute("SELECT store_id FROM account WHERE ID = %s", (user_id,))
        user_data = cursor.fetchone()
        store_id = user_data["store_id"] if user_data else None

        if not store_id:
            flash("❌ 店舗情報が紐付いていません。", "danger")
            return redirect(url_for("calendar.calendar"))

        # ==========================================================
        # ヘルパー関数: 時間フォーマット変換
        # ==========================================================
        def safe_time_format(val):
            if val is None: return "00:00"
            if hasattr(val, 'strftime'): return val.strftime("%H:%M")
            if hasattr(val, 'total_seconds'):
                total_seconds = int(val.total_seconds())
                h, m = divmod(total_seconds, 3600)
                return f"{h:02d}:{m // 60:02d}"
            s = str(val)
            return s[:5] if ':' in s else "00:00"

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
            # ★追加
            deadline_day = request.form.get("deadline_day", 20) 

            cursor.execute("SELECT ID FROM shift_settings WHERE store_id = %s LIMIT 1", (store_id,))
            existing_id = cursor.fetchone()

            if existing_id:
                cursor.execute("""
                    UPDATE shift_settings
                    SET start_time=%s, end_time=%s, break_minutes=%s, interval_minutes=%s,
                        max_hours_per_day=%s, min_hours_per_day=%s, max_people_per_shift=%s,
                        auto_mode=%s, deadline_day=%s, updated_at=NOW()
                    WHERE ID = %s AND store_id = %s
                """, (start_time, end_time, break_minutes, interval_minutes,
                      max_hours_per_day, min_hours_per_day, max_people_per_shift, 
                      auto_mode, deadline_day, existing_id["ID"], store_id))
            else:
                cursor.execute("""
                    INSERT INTO shift_settings 
                    (store_id, start_time, end_time, break_minutes, interval_minutes, 
                     max_hours_per_day, min_hours_per_day, max_people_per_shift, auto_mode, deadline_day, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (store_id, start_time, end_time, break_minutes, interval_minutes,
                      max_hours_per_day, min_hours_per_day, max_people_per_shift, auto_mode, deadline_day))
            conn.commit()
            flash("✅ 基本設定を保存しました", "success")
            return redirect(url_for("makeshift.settings"))

        # --- GET: 画面表示処理 ---
        
        # 1. 基本設定
        cursor.execute("SELECT * FROM shift_settings WHERE store_id = %s LIMIT 1", (store_id,))
        settings_data = cursor.fetchone()
        
        if not settings_data:
            settings_data = {
                "start_time": "09:00", "end_time": "22:00", "break_minutes": 60,
                "interval_minutes": 15, "max_hours_per_day": 8, "min_hours_per_day": 0,
                "max_people_per_shift": 30, "auto_mode": "balance"
            }
        else:
            settings_data["start_time"] = safe_time_format(settings_data["start_time"])
            settings_data["end_time"] = safe_time_format(settings_data["end_time"])

        # 2. 役割リスト
        cursor.execute("SELECT * FROM positions WHERE store_id = %s", (store_id,))
        positions_list = cursor.fetchall()
        
        # 3. 需要リスト（表示用）
        cursor.execute("""
            SELECT d.time_slot, d.position_id, d.required_count, d.day_type, p.name as position_name
            FROM shift_demand d
            LEFT JOIN positions p ON d.position_id = p.id
            WHERE d.store_id = %s
            ORDER BY d.day_type, d.time_slot, d.position_id
        """, (store_id,))
        raw_demands = cursor.fetchall()

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
                if r.get('day_type') == 'holiday':
                    holiday_demands.append(demand_item)
                else:
                    weekday_demands.append(demand_item)
        
        # 4. 特別営業時間
        cursor.execute("""
            SELECT date, start_time, end_time, reason 
            FROM special_hours 
            WHERE store_id = %s 
            ORDER BY date
        """, (store_id,))
        special_hours_list = cursor.fetchall()
        
        for sh in special_hours_list:
            if sh.get('start_time'): sh['start_time'] = safe_time_format(sh['start_time'])
            if sh.get('end_time'): sh['end_time'] = safe_time_format(sh['end_time'])
        
        return render_template("shift_setting.html", 
            settings=settings_data, 
            positions=positions_list, 
            weekday_demands=weekday_demands,
            holiday_demands=holiday_demands,
            special_hours=special_hours_list)

    except Exception as e:
        print(f"Settings Error: {e}")
        import traceback
        traceback.print_exc()
        return f"システムエラーが発生しました: {e}", 500
    finally:
        if conn:
            conn.close()
# ==========================================
# 3. 需要（ピークタイム）を追加する処理 (修正版: 平日/土日祝対応)-----------------------------------------------------------------------------------------
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
# 4. 需要をリセット（全削除）する処理-----------------------------------------------------------------------------------------
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
# 4.5 需要をリセット（全削除）する処理-----------------------------------------------------------------------------------------
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
# 4.8曜日タイプ別の需要リセット処理（新規追加）-----------------------------------------------------------------------------------------
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
from flask import Blueprint, render_template, redirect, url_for, session, request, flash, jsonify
import mysql.connector
from datetime import datetime, timedelta, time

# Blueprint定義（すでにある場合は飛ばしてください）
# makeshift_bp = Blueprint("makeshift", __name__, url_prefix="/makeshift")

# ==========================================
# 🛠️ ヘルパー関数: 時間・日付の安全なフォーマット
# ==========================================
def safe_time_format(val):
    """
    timedelta, time, str など、どんな型が来ても 'HH:MM' 形式の文字列に変換する
    """
    if val is None:
        return None
    
    # datetime.time 型の場合
    if isinstance(val, time):
        return val.strftime("%H:%M")
    
    # datetime.timedelta 型の場合（MySQLのTIME型はこれになることが多い）
    if isinstance(val, timedelta):
        total_seconds = int(val.total_seconds())
        h, m = divmod(total_seconds, 3600)
        return f"{h:02d}:{m // 60:02d}"
    
    # 文字列の場合
    s = str(val)
    # "09:00:00" -> "09:00"
    if ':' in s and len(s) > 5:
        return s[:5]
    return s

def safe_date_format(val):
    """
    date, datetime, str 型を 'YYYY-MM-DD' 形式に変換する
    """
    if val is None:
        return None
    if hasattr(val, 'strftime'):
        return val.strftime("%Y-%m-%d")
    return str(val)


# ==========================================
# 5. 確定シフト取得API (管理者用: 全員分)
# ==========================================
@makeshift_bp.route("/api/shifts/all")
def get_all_confirmed_shifts():
    # ★セキュリティ: 管理者ログインしていなければ弾く
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT s.user_id, a.name AS user_name, s.date, s.start_time, s.end_time, s.type
            FROM shift_table s
            JOIN account a ON s.user_id = a.ID
            WHERE s.user_id > 0  -- 負のID（不足枠）は除外したい場合
            ORDER BY s.date, s.start_time
        """)
        confirmed_shifts = cursor.fetchall()

        formatted_shifts = []
        for shift in confirmed_shifts:
            formatted_shifts.append({
                "user_id": shift["user_id"],
                "user_name": shift["user_name"],
                "date": safe_date_format(shift["date"]),
                "start_time": safe_time_format(shift["start_time"]),
                "end_time": safe_time_format(shift["end_time"]),
                "type": shift["type"]
            })
            
        return jsonify({"shifts": formatted_shifts})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ==========================================
# 👤 ユーザー個人用シフト取得API (公開制御付き)
# ==========================================
@makeshift_bp.route("/api/shifts/user/<int:user_id>")
def get_user_shifts(user_id):
    """
    ユーザーのシフト情報を取得するAPI。
    【重要】公開フラグ(shift_publish_status)をチェックし、未公開のシフトは隠蔽します。
    """
    
    # ★セキュリティ: 本人または管理者以外は見られないようにする
    current_user_id = session.get("user_id")
    # ※管理者の判定ロジックがあればここで「or is_admin」を追加してください
    if not current_user_id:
         return jsonify({"error": "Login required"}), 401
    
    # 今回は簡易的に「ログインしていれば自分のIDと一致するか」だけチェック
    # (管理者が見る場合はこのチェックを外すか、条件を緩和してください)
    if int(current_user_id) != user_id:
         # 管理者機能として見る場合はここをコメントアウトしてもOK
         pass 

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 1. ユーザー情報と店舗IDを取得
        cursor.execute("SELECT name, store_id FROM account WHERE ID = %s", (user_id,))
        user_data = cursor.fetchone()
        
        if not user_data:
            return jsonify({"error": "User not found"}), 404
            
        store_id = user_data['store_id']
        
        # 2. 【公開制御】公開済みの月を取得
        cursor.execute("""
            SELECT target_month FROM shift_publish_status 
            WHERE store_id = %s AND is_published = 1
        """, (store_id,))
        published_rows = cursor.fetchall()
        
        # 検索用セットを作成 (例: {'2025-01', '2025-02'})
        published_months = {row['target_month'] for row in published_rows}

        # 3. シフトデータを取得 (負のIDは除外)
        cursor.execute("""
            SELECT user_id, date, start_time, end_time, type
            FROM shift_table
            WHERE user_id = %s AND user_id > 0
            ORDER BY date, start_time
        """, (user_id,))
        raw_shifts = cursor.fetchall()
        
        # 4. フィルタリングとフォーマット
        formatted_shifts = []
        current_month_str = datetime.now().strftime("%Y-%m") # 今月 "2026-01"

        for shift in raw_shifts:
            # 日付を文字列化
            date_str = safe_date_format(shift["date"])
            month_str = date_str[:7] # "2026-01-25" -> "2026-01"
            
            # 【表示条件の修正】
            # 修正前: month_str < current_month_str (先月まで)
            # 修正後: month_str <= current_month_str (今月までOK！)
            # これで1月はボタンを押さなくても表示され、2月は隠れます。
            if (month_str in published_months) or (month_str <= current_month_str):
                
                formatted_shifts.append({
                    "user_id": shift["user_id"],
                    "user_name": user_data["name"],
                    "date": date_str,
                    "start_time": safe_time_format(shift["start_time"]),
                    "end_time": safe_time_format(shift["end_time"]),
                    "type": shift["type"]
                })
        # レスポンス作成
        # published_months も返しておくと、JS側で「工事中」表示に使えます
        response = {
            "user_id": user_id,
            "user_name": user_data["name"],
            "shifts": formatted_shifts,
            "published_months": list(published_months) 
        }
        
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ==========================================
# 🐞 デバッグ用: 全シフト確認 (開発中のみ使用推奨)
# ==========================================
@makeshift_bp.route("/api/debug/shifts_all")
def debug_all_shifts():
    # 本番環境ではこのルートを削除するか、管理者制限をかけること！
    if "user_id" not in session: return jsonify({"error": "Login required"}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT s.user_id, a.name as user_name, s.date, s.start_time, s.end_time, s.type
            FROM shift_table s
            LEFT JOIN account a ON s.user_id = a.ID
            ORDER BY s.date DESC, s.start_time
            LIMIT 100
        """)
        all_shifts = cursor.fetchall()
        
        formatted = []
        for shift in all_shifts:
            formatted.append({
                "user_id": shift["user_id"],
                "user_name": shift["user_name"] or "未定", # user_id < 0 の場合など
                "date": safe_date_format(shift["date"]),
                "start_time": safe_time_format(shift["start_time"]),
                "end_time": safe_time_format(shift["end_time"]),
                "type": shift["type"]
            })
        
        return jsonify({
            "count": len(formatted),
            "shifts": formatted
        })
    finally:
        conn.close()


# ==========================================
# 📱 従業員向けシフト確認画面 (HTML)
# ==========================================
@makeshift_bp.route("/user_shift_view/<int:user_id>")
def show_user_shift_view(user_id):
    # ログインチェック
    if "user_id" not in session:
        return redirect(url_for("login.login"))
    
    # ★セキュリティ: 他人のシフト閲覧防止
    # ログイン中のユーザーIDと、URLのuser_idが違う場合は自分のページへ飛ばす
    current_user_id = session["user_id"]
    if int(current_user_id) != user_id:
        flash("他のユーザーのページにはアクセスできません。", "warning")
        return redirect(url_for("makeshift.show_user_shift_view", user_id=current_user_id))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT name FROM account WHERE ID = %s", (user_id,))
        user_data = cursor.fetchone()
        
        if not user_data:
            return "ユーザーが見つかりません。", 404

        return render_template("user_shift_view.html", 
                             user_id=user_id, 
                             user_name=user_data['name'])
    finally:
        conn.close()

# ==========================================
# 特別営業時間の追加----------------------------------------------------------------------------------------
# ==========================================
@makeshift_bp.route("/settings/special_hours/add", methods=["POST"])
def add_special_hours():
    # AJAXリクエストかどうかを判定
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # 1. ログイン確認
    if "user_id" not in session:
        if is_ajax: return jsonify({'success': False, 'message': 'ログインが必要です'}), 401
        else:
            flash("ログインが必要です", "danger")
            return redirect(url_for('login.login'))
    
    user_id = session["user_id"]

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # ------------------------------------------
        # ★重要修正: account テーブルから store_id を取得
        # ------------------------------------------
        cursor.execute("SELECT store_id FROM account WHERE ID = %s", (user_id,))
        user_data = cursor.fetchone()
        
        # 店舗IDが取れない場合はエラー
        store_id = user_data["store_id"] if user_data else None

        if not store_id:
            print("Error: Store ID not found for user", user_id) # デバッグ表示
            if is_ajax: return jsonify({'success': False, 'message': '店舗情報が取得できませんでした'}), 400
            else:
                flash("店舗情報が取得できませんでした", "danger")
                return redirect(url_for('makeshift.settings'))
        
        # データの取得
        if is_ajax:
            data = request.get_json()
            date = data.get('date')
            start_time = data.get('start_time')
            end_time = data.get('end_time')
            reason = data.get('reason', '')
        else:
            date = request.form.get("date")
            start_time = request.form.get("start_time")
            end_time = request.form.get("end_time")
            reason = request.form.get("reason", "")
        
        # ------------------------------------------
        # ★重要修正: store_id を含めて保存
        # ------------------------------------------
        print(f"Saving special hours: StoreID={store_id}, Date={date}") # デバッグ表示

        cursor.execute("""
            INSERT INTO special_hours (store_id, date, start_time, end_time, reason, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE 
                start_time = VALUES(start_time),
                end_time = VALUES(end_time),
                reason = VALUES(reason)
        """, (store_id, date, start_time, end_time, reason))
        
        conn.commit()
        
        if is_ajax:
            return jsonify({
                'success': True,
                'message': f'✅ {date} の特別時間を設定しました',
                'data': {'date': date, 'start_time': start_time, 'end_time': end_time, 'reason': reason}
            }), 200
        else:
            flash(f"✅ {date} の特別時間を設定しました", "success")
            return redirect(url_for('makeshift.settings'))
        
    except Exception as e:
        conn.rollback()
        print(f"Special Hours Save Error: {e}") # ターミナルにエラー詳細を出す
        import traceback
        traceback.print_exc() # 詳細なエラーログ
        
        if is_ajax: return jsonify({'success': False, 'message': '保存に失敗しました'}), 500
        else:
            flash("設定の保存に失敗しました", "danger")
            return redirect(url_for('makeshift.settings'))
    finally:
        conn.close()


# ==========================================
# 特別営業時間の削除（修正版）----------------------------------------------------------------------------------------
# ==========================================
@makeshift_bp.route("/settings/special_hours/delete", methods=["POST"])
def delete_special_hours():
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if "user_id" not in session:
        if is_ajax: return jsonify({'success': False, 'message': 'ログインが必要です'}), 401
        else: return redirect(url_for('login.login'))
    
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # account テーブルから取得
        cursor.execute("SELECT store_id FROM account WHERE ID = %s", (user_id,))
        user_data = cursor.fetchone()
        store_id = user_data["store_id"] if user_data else None
    
        if not store_id:
            if is_ajax: return jsonify({'success': False, 'message': '店舗情報エラー'}), 400
            else:
                flash("店舗情報が取得できませんでした", "danger")
                return redirect(url_for('makeshift.settings'))
        
        if is_ajax:
            data = request.get_json()
            date = data.get('date')
        else:
            date = request.form.get("date")
        
        # 削除実行
        cursor.execute("DELETE FROM special_hours WHERE store_id = %s AND date = %s", (store_id, date))
        conn.commit()
        
        if is_ajax:
            return jsonify({'success': True, 'message': f'✅ {date} の特別設定を削除しました'}), 200
        else:
            flash(f"✅ {date} の特別設定を削除しました", "success")
            return redirect(url_for('makeshift.settings'))
        
    except Exception as e:
        conn.rollback()
        print(f"Delete Special Hours Error: {e}")
        if is_ajax: return jsonify({'success': False, 'message': '削除に失敗しました'}), 500
        else:
            flash("削除に失敗しました", "danger")
            return redirect(url_for('makeshift.settings'))
    finally:
        conn.close()
#---------------------------------------------------------------------------------------------------------------------------------
# ==========================================
# 📢 シフト公開・非公開切り替えAPI
# ==========================================
@makeshift_bp.route("/api/publish_status", methods=["POST"])
def toggle_publish_status():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "ログインが必要です"}), 401
    
    data = request.json
    target_month = data.get("month")   # 例: "2026-02"
    status = data.get("status")        # 1: 公開, 0: 非公開
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # ログインユーザーの店舗IDを取得
        cursor.execute("SELECT store_id FROM account WHERE ID = %s", (session["user_id"],))
        user_data = cursor.fetchone()
        store_id = user_data["store_id"] if user_data else None
        
        if not store_id:
            return jsonify({"success": False, "message": "店舗情報が見つかりません"}), 400

        # 公開状態を保存（ON DUPLICATE KEY で、あれば更新、なければ挿入）
        cursor.execute("""
            INSERT INTO shift_publish_status (store_id, target_month, is_published)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE is_published = VALUES(is_published)
        """, (store_id, target_month, status))
        
        conn.commit()
        msg = "公開しました" if status == 1 else "非公開にしました"
        return jsonify({"success": True, "message": f"{target_month}のシフトを{msg}"})
        
    except Exception as e:
        print(f"Publish Error: {e}")
        return jsonify({"success": False, "message": "更新に失敗しました"}), 500
    finally:
        cursor.close()
        conn.close()