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

@makeshift_bp.route("/auto_calendar")
def auto_calendar():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 0. 初期データ取得と設定の準備
        cursor.execute("SELECT * FROM shift_settings LIMIT 1")
        settings = cursor.fetchone()
        if not settings:
            return render_template("auto_calendar.html", message="シフト設定が未登録です。", shifts=[], settings={})

        settings['start_time'] = format_time(settings.get('start_time'))
        settings['end_time'] = format_time(settings.get('end_time'))
        if settings.get('updated_at') and isinstance(settings['updated_at'], (datetime, date_cls)):
            settings['updated_at'] = settings['updated_at'].strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("SELECT ID, name FROM account")
        users_data = cursor.fetchall()
        user_ids = [str(u['ID']) for u in users_data]
        num_users = len(user_ids)
        user_map = {user_id: i for i, user_id in enumerate(user_ids)}
        if num_users == 0:
            return render_template("auto_calendar.html", message="登録ユーザーがいません。", shifts=[], settings=settings)

        # 1. 処理対象となる全ての日付を取得 (希望が登録されている日付のみ)
        cursor.execute("SELECT DISTINCT date FROM calendar WHERE work = 1 ORDER BY date")
        target_dates = [row['date'] for row in cursor.fetchall()]

        # ⚠️ 修正: シフト生成前にshift_table全体をクリアし、古いシフト表示を防ぐ
        cursor.execute("DELETE FROM shift_table")
        conn.commit()
        
        if not target_dates:
            conn.close()
            return render_template("auto_calendar.html", message="希望シフトが登録されていません。", shifts=[], settings=settings)

        all_generated_shifts = []

        # === 3. 日付ごとのシフト生成ループ ===
        for target_date_obj in target_dates:
            target_date_str = target_date_obj.strftime("%Y-%m-%d")

            # 3.1. その日付の希望シフトのみを取得
            cursor.execute("""
                SELECT ID, date, start_time, end_time, work 
                FROM calendar 
                WHERE date = %s AND work = 1
            """, (target_date_str,))
            preference_rows = cursor.fetchall()
            
            # 3.2. 時間枠の定義と定数化
            SHIFT_START = ensure_time_obj(settings['start_time'])
            SHIFT_END = ensure_time_obj(settings['end_time'])
            INTERVAL_MINUTES = settings['interval_minutes']
            MAX_PEOPLE = settings['max_people_per_shift']

            # ⚠️ 最小勤務時間制約を完全に解除 (0時間)
            MIN_WORK_INTERVALS = 0 
            
            MAX_WORK_INTERVALS = settings['max_hours_per_day'] * 60 // INTERVAL_MINUTES
            
            # ⚠️ 休憩制約は無効化するため、関連定数も無視
            BREAK_MINUTES = settings['break_minutes']
            BREAK_REQUIRED_HOURS = 5 
            BREAK_REQUIRED_INTERVALS = BREAK_REQUIRED_HOURS * 60 // INTERVAL_MINUTES
            BREAK_INTERVALS = BREAK_MINUTES // INTERVAL_MINUTES
            # ---------------------------------------------------------------------

            time_intervals = []
            current_time_dt = datetime.combine(date_cls.today(), SHIFT_START)
            end_time_dt = datetime.combine(date_cls.today(), SHIFT_END)
            while current_time_dt < end_time_dt:
                time_intervals.append(current_time_dt.time())
                current_time_dt += timedelta(minutes=INTERVAL_MINUTES)
            num_intervals = len(time_intervals)

            if num_intervals == 0: continue 

            # 3.3. OR-Tools モデル構築と決定変数定義
            model = cp_model.CpModel()
            shifts = {}
            break_starts = {} 
            for u_idx in range(num_users):
                for t_idx in range(num_intervals):
                    shifts[u_idx, t_idx] = model.NewBoolVar(f's_{u_idx}_{t_idx}_{target_date_str}')
                    break_starts[u_idx, t_idx] = model.NewBoolVar(f'b_start_{u_idx}_{t_idx}_{target_date_str}')
                    
            total_work_intervals = {}
            for u_idx in range(num_users):
                total_work_intervals[u_idx] = model.NewIntVar(0, num_intervals, f'total_w_{u_idx}_{target_date_str}')
                model.Add(total_work_intervals[u_idx] == sum(shifts[u_idx, t_idx] for t_idx in range(num_intervals)))

            # 3.4. 制約の追加
            
            # 4-1. 時間帯最大人数制約 (MAX_PEOPLEは上限として機能)
            for t_idx in range(num_intervals):
                model.Add(sum(shifts[u_idx, t_idx] for u_idx in range(num_users)) <= MAX_PEOPLE)
                
            # 4-2. 最小・最大勤務時間制約 (最小勤務は0時間に設定)
            for u_idx in range(num_users):
                model.Add(total_work_intervals[u_idx] >= MIN_WORK_INTERVALS) # 0時間
                model.Add(total_work_intervals[u_idx] <= MAX_WORK_INTERVALS) # 最大時間

            # 4-3. ユーザーの希望シフト制約 (厳格な禁止制約を復活 + バグ修正)
            user_preferences_map = {} 
            preference_fulfillment = []
            
            # ⚠️ 最終バグ修正: 希望シフトが全くないユーザーを特定し、全時間帯を禁止する
            users_with_preference = {row['ID'] for row in preference_rows}
            
            for u_idx, u_id in enumerate(user_ids):
                if u_id not in users_with_preference:
                    # このユーザーは希望シフトを登録していないため、全ての時間帯を勤務禁止
                    for t_idx in range(num_intervals):
                        model.Add(shifts[u_idx, t_idx] == 0)


            for row in preference_rows:
                u_id = row['ID']
                if u_id not in user_map: continue
                u_idx = user_map[u_id]
                start_t = ensure_time_obj(row['start_time'])
                end_t = ensure_time_obj(row['end_time'])
                
                if u_idx not in user_preferences_map: user_preferences_map[u_idx] = set()

                for t_idx, t_time in enumerate(time_intervals):
                    # 勤務希望時間帯
                    if start_t <= t_time < end_t:
                        user_preferences_map[u_idx].add(t_idx)
                        preference_fulfillment.append(shifts[u_idx, t_idx])
                    # 勤務禁止時間帯
                    else:
                        # ⚠️ 厳格な制約: 希望外は勤務不可
                        model.Add(shifts[u_idx, t_idx] == 0)
                        
            # 4-4. 休憩時間制約 (完全に無効化)
            pass

            # 3.5. 目的関数の定義 (バランスモードのみ使用、希望充足度と公平性)
            min_work = model.NewIntVar(0, num_intervals, 'min_work')
            max_work = model.NewIntVar(0, num_intervals, 'max_work')
            
            if total_work_intervals:
                model.AddMaxEquality(max_work, total_work_intervals.values())
                model.AddMinEquality(min_work, total_work_intervals.values())
                fairness_cost = max_work - min_work 
            else:
                fairness_cost = 0

            # ⚠️ モードはバランスモードのみ使用
            model.Maximize(
                sum(preference_fulfillment) * PREFERENCE_REWARD_WEIGHT - 
                fairness_cost * FAIRNESS_PENALTY_WEIGHT
            )

            # 3.6. ソルバー実行と結果処理
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 5.0
            status = solver.Solve(model)
            
            shifts_to_save_day = []
            if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
                
                for u_idx in range(num_users):
                    user_id = user_ids[u_idx]
                    current_shift_start_time = None
                    
                    # 勤務時間 (work) の保存
                    for t_idx in range(num_intervals):
                        is_working = solver.Value(shifts[u_idx, t_idx]) == 1
                        t_time = time_intervals[t_idx]
                        
                        if is_working:
                            if current_shift_start_time is None:
                                current_shift_start_time = t_time
                            
                            # シフトの終わりを判定
                            if t_idx == num_intervals - 1 or solver.Value(shifts[u_idx, t_idx + 1]) == 0:
                                end_t_dt = datetime.combine(target_date_obj, t_time) + timedelta(minutes=INTERVAL_MINUTES)
                                shifts_to_save_day.append({
                                    "user_id": user_id, "date": target_date_str,
                                    "start_time": to_time_str(current_shift_start_time),
                                    "end_time": to_time_str(end_t_dt.time()),
                                    "type": "work"
                                })
                                current_shift_start_time = None
                    
                    # 休憩時間は無効化されたため、処理を省略
                    pass 
                
                all_generated_shifts.extend(shifts_to_save_day)
            
            elif status != cp_model.OPTIMAL and status != cp_model.FEASIBLE:
                status_name = solver.StatusName(status)
                conn.close()
                return render_template("auto_calendar.html", 
                settings=settings, 
                shifts=[],
                message=f"最適な解が見つかりませんでした。(Status: {status_name})。これは、**人数、希望、最大勤務時間**の制約が同時に満たせないことを意味します。",
                error_details=f"Target Date: {target_date_str}, Status: {status_name}")


        # === 4. ループ終了後の最終処理 ===
        if all_generated_shifts:
            sql = "INSERT INTO shift_table (user_id, date, start_time, end_time, type) VALUES (%s, %s, %s, %s, %s)"
            insert_data = [(s['user_id'], s['date'], s['start_time'], s['end_time'], s['type']) for s in all_generated_shifts]
            cursor.executemany(sql, insert_data)
            conn.commit()
            
            cursor.execute("SELECT user_id, date, start_time, end_time, type FROM shift_table ORDER BY date, start_time")
            final_shifts = cursor.fetchall()
            conn.close()
            
            formatted_shifts = [{
                "user_id": s['user_id'], 
                "date": s['date'].strftime("%Y-%m-%d"), 
                "start_time": format_time(s['start_time']), 
                "end_time": format_time(s['end_time']),     
                "type": s['type']
            } for s in final_shifts]

            return render_template("auto_calendar.html", 
            settings=settings, 
            shifts=formatted_shifts,
            message=f"{len(formatted_shifts)} 件のシフトを{len(target_dates)}日分自動生成しました。")

        else:
            conn.close()
            return render_template("auto_calendar.html", message="シフトが割り当てられませんでした。全員が勤務不可能な設定です。", shifts=[], settings=settings)

    except Exception as e:
        conn.close()
        error_trace = traceback.format_exc()
        print("--- SHIFT GENERATION ERROR ---")
        print(error_trace)
        print("------------------------------")
        
        return render_template("auto_calendar.html", 
        settings=settings, 
        shifts=[],
        message=f"予期せぬエラーが発生しました: {str(e)}",
        error_details=error_trace)
# === 設定画面 ===----------------------------------------------------------------------------------------------
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

#----------------------------------------------------------------------------------------------------------------------------

# === 既存の /api/shifts/all ルートを修正 ===
@makeshift_bp.route("/api/shifts/all")
def get_all_confirmed_shifts():
    """全ての日付・全ユーザーの確定シフトをJSON形式で返すAPI (user_nameを必ず取得)"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # ユーザー名を取得するためのJOINが必須
    cursor.execute("""
        SELECT 
            s.user_id, a.name AS user_name, s.date, s.start_time, s.end_time, s.type
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
    """特定のユーザーIDの確定シフトをJSON形式で返すAPI"""
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
        query = "SELECT ID, name FROM account"
        if busy_users:
            # IDが busy_users に含まれない人を抽出
            format_strings = ','.join(['%s'] * len(busy_users))
            query += f" WHERE ID NOT IN ({format_strings})"
            cursor.execute(query, tuple(busy_users))
        else:
            cursor.execute(query)
            
        eligible_staff = cursor.fetchall()
        
        conn.commit()

        # 3. Bot送信用にデータを返す
        # 実際のBot配信はこのレスポンスを受け取ったJavaScript側などでキックします
        return jsonify({
            "message": "募集を作成しました",
            "request_id": request_id,
            "target_count": len(eligible_staff),
            "targets": eligible_staff,  # このリストに向けてLINE等を送る
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