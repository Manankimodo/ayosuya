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
            """時刻を文字列に変換"""
            if val is None: 
                return "00:00"
            if hasattr(val, 'strftime'): 
                return val.strftime("%H:%M")
            if hasattr(val, 'total_seconds'):
                total_seconds = int(val.total_seconds())
                h, m = divmod(total_seconds, 3600)
                return f"{h:02d}:{m:02d}"
            s = str(val)
            return s[:5] if ':' in s else "00:00"

        def safe_to_time(val):
            """値をtime型に変換"""
            if val is None: 
                return time(0, 0)
            if isinstance(val, time): 
                return val
            if isinstance(val, timedelta): 
                return (datetime.min + val).time()
            s = str(val).strip()
            try: 
                return datetime.strptime(s, "%H:%M:%S").time()
            except: 
                pass
            try: 
                return datetime.strptime(s, "%H:%M").time()
            except: 
                pass
            return time(0, 0)

        # ========================================================
        # 2. target_month パラメータの取得（提出期限考慮版）
        # ========================================================
        target_month = request.args.get('target_month', type=int)

        # まず設定から提出期限日を取得
        cursor.execute("SELECT deadline_day FROM shift_settings LIMIT 1")
        deadline_row = cursor.fetchone()
        deadline_day = deadline_row.get('deadline_day', 13) if deadline_row else 13

        print(f"DEBUG: 取得した締切日 = {deadline_day}")

        if not target_month:
            today = datetime.now()
            
            print(f"DEBUG: 今日の日付 = {today}, 今日の日 = {today.day}")
            
            # 提出期限を考慮した対象月の計算
            if today.day > deadline_day:
                print(f"DEBUG: 締切過ぎている ({today.day} > {deadline_day})")
                # 既に今月の締切を過ぎている → 再来月を対象
                if today.month == 11:
                    target_month = 1
                    target_year = today.year + 1
                elif today.month == 12:
                    target_month = 2
                    target_year = today.year + 1
                else:
                    target_month = today.month + 2
                    target_year = today.year
            else:
                print(f"DEBUG: まだ締切前 ({today.day} <= {deadline_day})")
                # まだ今月の締切前 → 来月を対象
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

        print(f"DEBUG: 最終決定 → 対象月={target_month}, 対象年={target_year}")

        # ========================================================
        # 3. 設定取得
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
            "auto_mode": row.get("auto_mode", "balance"),
            "deadline_day": row.get("deadline_day", 13)
        }

        SHIFT_START = safe_to_time(settings['start_time'])
        SHIFT_END = safe_to_time(settings['end_time'])
        INTERVAL_MINUTES = int(settings['interval_minutes'])
        settings['start_time'] = SHIFT_START.strftime("%H:%M")
        settings['end_time'] = SHIFT_END.strftime("%H:%M")

        # ========================================================
        # 4. ユーザー情報の取得
        # ========================================================
        cursor.execute("SELECT ID, name FROM account")
        users_data = cursor.fetchall()
        user_ids = [str(u['ID']) for u in users_data]
        num_users = len(user_ids)
        user_map = {str(user_id): i for i, user_id in enumerate(user_ids)}
        
        # 役割名マッピング
        position_names = {}
        cursor.execute("SELECT id, name FROM positions")
        for p in cursor.fetchall():
            # 安全性チェック追加
            if p.get('id') is not None and p.get('name') is not None:
                position_names[str(p['id'])] = p['name']

        print(f"DEBUG: 取得した役割: {position_names}")

        # ユーザーのスキル（役割）取得
        user_skill_ids = {}
        cursor.execute("SELECT user_id, position_id FROM user_positions")
        for row in cursor.fetchall():
            # 安全性チェック追加
            if row.get('user_id') is None or row.get('position_id') is None:
                print(f"WARNING: user_positions に null データ: {row}")
                continue
            uid = str(row['user_id'])
            pid = str(row['position_id'])
            if uid not in user_skill_ids: 
                user_skill_ids[uid] = []
            user_skill_ids[uid].append(pid)

        # 需要データ取得（平日・休日別）
        demand_weekday = {}
        demand_weekend = {}
        cursor.execute("SELECT time_slot, position_id, required_count, day_type FROM shift_demand")
        for row in cursor.fetchall():
            # 安全性チェック追加
            if row.get('time_slot') is None or row.get('position_id') is None:
                print(f"WARNING: shift_demand に null データ: {row}")
                continue
            t_str = safe_to_time(row['time_slot']).strftime("%H:%M")
            pid = str(row['position_id'])
            day_type = row.get('day_type', 'weekday')
            target_map = demand_weekend if day_type == 'holiday' else demand_weekday
            if t_str not in target_map: 
                target_map[t_str] = {}
            target_map[t_str][pid] = row['required_count']
        
        print(f"DEBUG: 平日需要データ数: {len(demand_weekday)}, 休日需要データ数: {len(demand_weekend)}")

        # ========================================================
        # 5. 対象月のデータ取得
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
        # 6. 削除処理
        # ========================================================
        if mode == 'reset':
            # 完全リセット
            sql = f"DELETE FROM shift_table WHERE date IN ({placeholders})"
            cursor.execute(sql, tuple(dates_list))
            print(f"DEBUG: 完全リセット - 削除件数: {cursor.rowcount}")
        elif mode == 'unlock_all':
            # 全保護解除
            sql = f"UPDATE shift_table SET is_locked = 0 WHERE date IN ({placeholders}) AND CAST(user_id AS SIGNED) > 0"
            cursor.execute(sql, tuple(dates_list))
            print(f"DEBUG: 全保護解除 - 更新件数: {cursor.rowcount}")
        else:
            # 通常削除（保護されていないシフトと不足データのみ）
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
        
        # unlock_allモードの場合はここで終了
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
        # 7. 日付ごとの最適化ループ
        # ========================================================
        for target_date_obj in target_dates:
            target_date_str = target_date_obj.strftime("%Y-%m-%d")
            
            # 平日・休日判定
            is_weekend = target_date_obj.weekday() >= 5
            demand_map = demand_weekend if is_weekend else demand_weekday
            
            day_type_str = "休日" if is_weekend else "平日"
            total_demand = sum(sum(d.values()) for d in demand_map.values())
            print(f"DEBUG: {target_date_str}({day_type_str}) - 需要時間帯数: {len(demand_map)}, 総需要: {total_demand}")
            
            # ========================================================
            # 8. グローバルスキル希少性の計算（★役割タイプ追加★）
            # ========================================================
            # 役割名とタイプのマッピング
            position_names = {}
            position_types = {}

            cursor.execute("SELECT id, name, priority_type FROM positions")
            for p in cursor.fetchall():
                # 安全性チェック追加
                if p.get('id') is not None and p.get('name') is not None:
                    pid = str(p['id'])
                    position_names[pid] = p['name']
                    position_types[pid] = p.get('priority_type', 'normal')

            print(f"DEBUG: 取得した役割: {[(position_names[pid], position_types[pid]) for pid in position_names.keys()]}")

            # 各スキルを持っている人数を事前計算
            skill_holder_count = {}
            for pid in position_names.keys():
                count = sum(1 for uid in user_ids if pid in user_skill_ids.get(uid, []))
                skill_holder_count[pid] = count if count > 0 else 999

            print(f"DEBUG: スキル保有者数: {[(position_names.get(pid), position_types.get(pid), cnt) for pid, cnt in skill_holder_count.items()]}")

            # 時間インターバル生成
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

            # 保護されたシフト取得
            cursor.execute("""
                SELECT user_id, start_time, end_time, type 
                FROM shift_table 
                WHERE date = %s AND is_locked = 1 AND CAST(user_id AS SIGNED) > 0
            """, (target_date_str,))
            locked_shifts_data = cursor.fetchall()

            locked_user_ids_set = set()
            for ls in locked_shifts_data:
                locked_user_ids_set.add(str(ls['user_id']))
            # ========================================================
            # 9. CP-SAT モデル構築
            # ========================================================
            model = cp_model.CpModel()
            
            # 変数: shifts[user, time_interval]
            shifts = {}
            for u in range(num_users):
                for t in range(num_intervals):
                    shifts[u, t] = model.NewBoolVar(f's_{u}_{t}')

            # 保護されたシフトの制約
            user_locked_map = {u_idx: [False] * num_intervals for u_idx in range(num_users)}

            for ls in locked_shifts_data:
                uid_str = str(ls['user_id'])
                if uid_str not in user_map: 
                    continue
                u_idx = user_map[uid_str]
                l_start = safe_to_time(ls['start_time'])
                l_end = safe_to_time(ls['end_time'])
                
                for t_idx, t_time in enumerate(time_intervals):
                    if l_start <= t_time < l_end:
                        user_locked_map[u_idx][t_idx] = True

            # ========================================================
            # 10. 需要充足制約
            # ========================================================
            demand_fulfillment = []
            over_staff_penalty = []

            for t_idx, t_time in enumerate(time_intervals):
                t_str = t_time.strftime("%H:%M")
                
                if t_str in demand_map:
                    current_demand = demand_map[t_str]
                    
                    for pid, count in current_demand.items():
                        # このスキルを持つユーザーのみ
                        capable = [shifts[u, t_idx] for u in range(num_users) 
                                   if pid in user_skill_ids.get(user_ids[u], [])]
                        
                        if capable:
                            actual_count = sum(capable)
                            model.Add(actual_count <= count)
                            
                            # 需要充足度
                            capped_count = model.NewIntVar(0, count, f'capped_{t_str}_{pid}')
                            model.Add(capped_count <= actual_count)
                            model.Add(capped_count <= count)
                            demand_fulfillment.append(capped_count)

                            # 過剰人員ペナルティ
                            excess_count = model.NewIntVar(0, 2, f'excess_{t_str}_{pid}')
                            model.Add(excess_count == actual_count - capped_count)
                            over_staff_penalty.append(excess_count)

                # 総人数上限制約
                total_req = sum(demand_map[t_str].values()) if t_str in demand_map else 0
                current_total_shifts = sum(shifts[u, t_idx] for u in range(num_users))
                
                if total_req == 0:
                    model.Add(current_total_shifts == 0)
                else:
                    model.Add(current_total_shifts <= total_req)

            # ========================================================
            # 11. 労働時間制約
            # ========================================================
            max_hours = float(settings['max_hours_per_day'])
            max_intervals = int((max_hours * 60) / INTERVAL_MINUTES)
            min_hours = float(settings.get('min_hours_per_day', 0))
            min_slots = int((min_hours * 60) / INTERVAL_MINUTES)

            user_total_hours = []
            for u in range(num_users):
                total_worked = sum(shifts[u, t] for t in range(num_intervals))
                user_total_hours.append(total_worked)
                
                # 最大時間制約（ハード制約）
                model.Add(total_worked <= max_intervals)

            # バランス制約（最大・最小労働時間の差を最小化）
            max_hours_var = model.NewIntVar(0, max_intervals, 'max_hours')
            min_hours_var = model.NewIntVar(0, max_intervals, 'min_hours')

            for total in user_total_hours:
                model.Add(max_hours_var >= total)
                is_working_user = model.NewBoolVar(f'is_working_check')
                model.Add(total > 0).OnlyEnforceIf(is_working_user)
                model.Add(total == 0).OnlyEnforceIf(is_working_user.Not())
                model.Add(min_hours_var <= total).OnlyEnforceIf(is_working_user)

            balance_penalty = max_hours_var - min_hours_var

            # ========================================================
            # 12. 連続勤務制約（中抜け防止）
            # ========================================================
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
                
                # 保護シフトがある場合のみ2ブロックまで許可（既存のロックを尊重）
                if str(user_ids[u]) in locked_user_ids_set:
                    model.Add(sum(start_flags) <= 2)
                else:
                    model.Add(sum(start_flags) <= 1)

            # ========================================================
            # 13. 希望シフト取得とログ出力
            # ========================================================
            cursor.execute("""
                SELECT ID, start_time, end_time 
                FROM calendar 
                WHERE date = %s AND work = 1
            """, (target_date_str,))
            preference_rows = cursor.fetchall()

            # 希望時間帯マップを作成
            user_pref_intervals = {}
            for row in preference_rows:
                uid_str = str(row['ID'])
                if uid_str not in user_map:
                    continue
                u_idx = user_map[uid_str]
                
                s_val = safe_to_time(row['start_time'])
                e_val = safe_to_time(row['end_time'])
                
                user_pref_intervals[u_idx] = []
                for t_idx, t_val in enumerate(time_intervals):
                    if s_val <= t_val < e_val:
                        user_pref_intervals[u_idx].append(t_idx)

            print(f"DEBUG: {target_date_str} - 希望シフト登録者数: {len(preference_rows)}")

            # ★修正: 希望外の時間帯は完全に禁止 + 最低勤務時間チェック
            for u_idx in range(num_users):
                uid = user_ids[u_idx]
                
                # 保護シフトがある場合
                if str(uid) in locked_user_ids_set:
                    # 保護シフトの時間帯のみ1に固定、それ以外は0
                    for t_idx, is_locked in enumerate(user_locked_map[u_idx]):
                        if is_locked:
                            model.Add(shifts[u_idx, t_idx] == 1)
                        else:
                            model.Add(shifts[u_idx, t_idx] == 0)
                    continue
                
                # 希望シフト未登録の場合は全て0
                if u_idx not in user_pref_intervals:
                    for t in range(num_intervals):
                        model.Add(shifts[u_idx, t] == 0)
                else:
                    pref_times = set(user_pref_intervals[u_idx])
                    pref_duration = len(pref_times) * INTERVAL_MINUTES / 60  # 希望時間の長さ（時間）
                    
                    # ★追加: 希望時間が最低勤務時間より短い場合は配置しない
                    if min_hours > 0 and pref_duration < min_hours:
                        print(f"WARNING: User {uid} の希望時間({pref_duration:.1f}h)が最低勤務時間({min_hours}h)未満のため配置対象外")
                        for t in range(num_intervals):
                            model.Add(shifts[u_idx, t] == 0)
                    else:
                        # 希望時間帯以外は0に固定
                        for t in range(num_intervals):
                            if t not in pref_times:
                                model.Add(shifts[u_idx, t] == 0)

            
            # ========================================================
            # 14. 目的関数（スコア計算）
            # ========================================================

            # 希望開始時間ボーナス
            start_time_bonus = []
            # 希望時間帯の充足率ボーナス
            coverage_bonus = []

            for row in preference_rows:
                uid_str = str(row['ID'])
                if uid_str not in user_map:
                    continue
                u = user_map[uid_str]
                
                # ロック済みユーザーは計算対象外（既に確定しているため）
                if uid_str in locked_user_ids_set:
                    continue
                
                # ★追加: 最低勤務時間を満たさないユーザーもスキップ
                if u in user_pref_intervals:
                    pref_duration = len(user_pref_intervals[u]) * INTERVAL_MINUTES / 60
                    if min_hours > 0 and pref_duration < min_hours:
                        continue
                
                s_val = safe_to_time(row['start_time'])
                e_val = safe_to_time(row['end_time'])
                
                # 希望開始時間に最も近い時間帯を特定
                start_intervals = []
                for t, t_val in enumerate(time_intervals):
                    if s_val <= t_val < e_val:
                        start_intervals.append(t)
                
                if start_intervals:
                    # 希望開始時刻ちょうどから始まるボーナス
                    first_interval = start_intervals[0]
                    start_time_bonus.append(shifts[u, first_interval])
                    
                    # 希望時間帯全体をできるだけ埋めるボーナス
                    for t in start_intervals:
                        coverage_bonus.append(shifts[u, t])

            # --- 最近の勤務日数ペナルティ ---
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

            # 重み付け設定
            WEIGHT_DEMAND = 1000
            WEIGHT_START_TIME = 50
            WEIGHT_COVERAGE = 30
            WEIGHT_OVERSTAFF = 20
            WEIGHT_BALANCE = 3
            WEIGHT_RECENT_WORK = 2

            # 目的関数定義
            model.Maximize(
                sum(demand_fulfillment) * WEIGHT_DEMAND +
                sum(start_time_bonus) * WEIGHT_START_TIME +
                sum(coverage_bonus) * WEIGHT_COVERAGE -
                sum(over_staff_penalty) * WEIGHT_OVERSTAFF -
                balance_penalty * WEIGHT_BALANCE -
                sum(recent_work_penalty) * WEIGHT_RECENT_WORK
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

            # ========================================================
            # 16. 解析結果の処理
            # ========================================================
            if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                print(f"DEBUG: {target_date_str} - 配置されたユーザー数:")
                for u_idx in range(num_users):
                    total_slots = sum(solver.Value(shifts[u_idx, t]) for t in range(num_intervals))
                    if total_slots > 0:
                        user_id = user_ids[u_idx]
                        is_locked = "🔒" if user_id in locked_user_ids_set else ""
                        print(f"  - User {user_id}{is_locked}: {total_slots}スロット ({total_slots * INTERVAL_MINUTES / 60:.1f}時間)")
                
                user_assigned_roles = {}
                active_shortages = {}
                shortage_list_day = []

                # ========================================================
                # 17. 役割割り当てロジック（必須役割優先版）
                # ========================================================
                for t_idx, t_time in enumerate(time_intervals):
                    t_str = t_time.strftime("%H:%M")
                    
                    # 1. 勤務が決まったユーザーの抽出
                    working_users = []
                    locked_users_in_this_slot = []
                    for u_idx in range(num_users):
                        if solver.Value(shifts[u_idx, t_idx]) == 1:
                            if user_ids[u_idx] in locked_user_ids_set:
                                locked_users_in_this_slot.append(u_idx)
                            else:
                                working_users.append(u_idx)
                    
                    # 2. 需要枠（管理者の設定）をリスト化
                    open_slots = []
                    if t_str in demand_map:
                        for pid, count in demand_map[t_str].items():
                            for _ in range(count): 
                                open_slots.append(pid)
                    
                    # ========================================================
                    # ★3. 需要枠を優先度順にソート★
                    # ========================================================
                    def slot_priority(pid):
                        ptype = position_types.get(pid, 'normal')
                        if ptype == 'critical':
                            return 0
                        elif ptype == 'normal':
                            return 1
                        else:
                            return 2
                    
                    open_slots.sort(key=slot_priority)
                    
                    if len(open_slots) > 0 and len(open_slots) <= 10:
                        slot_summary = [f'{position_names.get(pid, "?")}({position_types.get(pid, "?")})' for pid in open_slots]
                        print(f"DEBUG: {t_str} 需要枠（優先度順）: {slot_summary}")
                    
                    # ========================================================
                    # ★4. 保護ユーザーの役割を先に割り当て★
                    # ========================================================
                    assigned_pids = {}
                    
                    for u_idx in locked_users_in_this_slot:
                        uid = user_ids[u_idx]
                        skills = user_skill_ids.get(uid, [])
                        
                        available_slots = [(i, pid) for i, pid in enumerate(open_slots) if pid in skills]
                        
                        if available_slots:
                            slot_idx, selected_pid = available_slots[0]
                            assigned_pids[u_idx] = selected_pid
                            open_slots.pop(slot_idx)
                            print(f"DEBUG: 🔒保護ユーザー {uid} → {position_names.get(selected_pid)}")
                        else:
                            assigned_pids[u_idx] = skills[0] if skills else "Staff"
                    
                    # ========================================================
                    # ★5. ユーザーのソート: 必須スキル保有者を優先★
                    # ========================================================
                    def user_priority(u_idx):
                        uid = user_ids[u_idx]
                        skills = user_skill_ids.get(uid, [])
                        
                        has_critical_skill = any(position_types.get(s) == 'critical' for s in skills)
                        
                        if has_critical_skill:
                            priority_tier = 0
                        else:
                            priority_tier = 1
                        
                        min_rarity = min([skill_holder_count.get(s, 999) for s in skills]) if skills else 999
                        
                        return (priority_tier, len(skills), min_rarity, u_idx)
                    
                    working_users.sort(key=user_priority)
                    
                    # ========================================================
                    # ★6. 通常ユーザーの役割割り当て★
                    # ========================================================
                    for u_idx in working_users:
                        uid = user_ids[u_idx]
                        skills = user_skill_ids.get(uid, [])
                        
                        available_slots = [(i, pid) for i, pid in enumerate(open_slots) if pid in skills]
                        
                        if available_slots:
                            shortage_count = {}
                            for pid in open_slots:
                                shortage_count[pid] = shortage_count.get(pid, 0) + 1
                            
                            slot_scores = []
                            for slot_idx, pid in available_slots:
                                ptype = position_types.get(pid, 'normal')
                                if ptype == 'critical':
                                    type_score = 1000
                                elif ptype == 'normal':
                                    type_score = 100
                                else:
                                    type_score = 10
                                
                                rarity_score = 100 / max(skill_holder_count.get(pid, 1), 1)
                                urgency_score = shortage_count.get(pid, 1) * 10
                                total_score = type_score + (rarity_score * 3) + (urgency_score * 2)
                                
                                slot_scores.append((slot_idx, pid, total_score))
                            
                            sorted_slots = sorted(slot_scores, key=lambda x: -x[2])
                            slot_idx, selected_pid, score = sorted_slots[0]
                            
                            assigned_pids[u_idx] = selected_pid
                            open_slots.pop(slot_idx)
                            
                            if len(working_users) <= 5:
                                p_name = position_names.get(selected_pid, "不明")
                                p_type = position_types.get(selected_pid, "normal")
                                type_icon = {"critical": "⭐", "normal": "📋", "support": "🔧"}.get(p_type, "")
                                print(f"    User {uid} → {type_icon}{p_name} (スコア: {score:.1f})")

                    # 7. 結果を記録
                    for u_idx, pid in assigned_pids.items():
                        if u_idx not in user_assigned_roles: 
                            user_assigned_roles[u_idx] = {}
                        
                        if t_str in demand_map and pid in [p for p in demand_map[t_str].keys()]:
                            user_assigned_roles[u_idx][t_idx] = position_names.get(pid, "Work")

                    # ========================================================
                    # 18. 不足データ生成
                    # ========================================================
                    remaining_open_slots = list(open_slots)
                    
                    print(f"DEBUG: {t_str} - 全需要: {len(demand_map.get(t_str, {}).values()) if t_str in demand_map else 0}, 配置済み: {len(assigned_pids)}, 残り不足: {len(remaining_open_slots)}")
                    
                    next_end_dt = (datetime.combine(base_date, t_time) + timedelta(minutes=INTERVAL_MINUTES)).time()
                    
                    # A. 継続中の不足を更新
                    for key in list(active_shortages.keys()):
                        pid = key.split('_')[0]
                        
                        if pid in remaining_open_slots:
                            active_shortages[key]['end_time'] = next_end_dt.strftime("%H:%M")
                            remaining_open_slots.remove(pid)
                        else:
                            shortage_list_day.append(active_shortages[key])
                            del active_shortages[key]
                    
                    # B. 新しく発生した不足を作成
                    for pid in remaining_open_slots:
                        n = 0
                        while f"{pid}_{n}" in active_shortages:
                            n += 1
                        
                        unique_key = f"{pid}_{n}"
                        p_name = position_names.get(pid, "役割")
                        
                        try:
                            unique_neg_id = -1 * (int(pid) * 1000 + n + 1)
                        except (ValueError, TypeError) as e:
                            print(f"ERROR: pidの変換に失敗: pid={pid}, type={type(pid)}, error={e}")
                            unique_neg_id = -1 * (hash(str(pid)) % 1000000)
                        
                        shortage_count_for_this_position = sum(1 for k in active_shortages.keys() if k.startswith(f"{pid}_"))
                        if shortage_count_for_this_position > 0 or remaining_open_slots.count(pid) > 1:
                            display_name = f"🚨 {p_name}不足 ({n+1})"
                        else:
                            display_name = f"🚨 {p_name}不足"
                        
                        active_shortages[unique_key] = {
                            "user_id": unique_neg_id, 
                            "user_name": display_name,
                            "date": target_date_str,
                            "start_time": t_time.strftime("%H:%M"),
                            "end_time": next_end_dt.strftime("%H:%M"), 
                            "type": display_name
                        }
                
                # 最終処理：閉店まで残った不足をすべて回収
                for item in active_shortages.values(): 
                    shortage_list_day.append(item)
                
                all_generated_shifts.extend(shortage_list_day)
                
                # ========================================================
                # 19. シフトブロック生成
                # ========================================================
                for u_idx, roles_map in user_assigned_roles.items():
                    user_id = user_ids[u_idx]
                    
                    if user_id in locked_user_ids_set:
                        continue
                        
                    current_block_start = None
                    current_role = None
                    
                    for t_idx in range(num_intervals):
                        role_name = roles_map.get(t_idx)
                        t_time = time_intervals[t_idx]
                        t_str = t_time.strftime("%H:%M")
                        
                        has_demand_for_this_role = False
                        if t_str in demand_map:
                            for pid, count in demand_map[t_str].items():
                                if position_names.get(pid) == role_name:
                                    has_demand_for_this_role = True
                                    break
                        
                        if role_name and has_demand_for_this_role:
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
            
            # ========================================================
            # 20. 最適化失敗時の処理
            # ========================================================
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
                            n = 0
                            while f"{pid}_{n}" in active_shortages:
                                n += 1
                            
                            key = f"{pid}_{n}"
                            next_end_dt = datetime.combine(base_date, t_time) + timedelta(minutes=INTERVAL_MINUTES)
                            
                            if key in active_shortages:
                                active_shortages[key]['end_time'] = next_end_dt.time().strftime("%H:%M")
                            else:
                                p_name = position_names.get(pid, "役割")
                                
                                try:
                                    unique_neg_id = -1 * (int(pid) * 1000 + n + 1)
                                except (ValueError, TypeError) as e:
                                    print(f"ERROR: pidの変換に失敗(失敗時): pid={pid}, type={type(pid)}, error={e}")
                                    unique_neg_id = -1 * (hash(str(pid)) % 1000000)
                                
                                if shortage > 1:
                                    unique_name = f"🚨 {p_name}不足 ({n+1})"
                                else:
                                    unique_name = f"🚨 {p_name}不足"
                                
                                active_shortages[key] = {
                                    "user_id": unique_neg_id,
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

        # ========================================================
        # 21. DB保存
        # ========================================================
        if all_generated_shifts:
            sql = "INSERT INTO shift_table (user_id, date, start_time, end_time, type, is_locked) VALUES (%s, %s, %s, %s, %s, %s)"
            data = [(s['user_id'], s['date'], s['start_time'], s['end_time'], s['type'], 0) 
                    for s in all_generated_shifts]
            cursor.executemany(sql, data)
            conn.commit()
            print(f"DEBUG: 新規シフト保存 - 件数: {len(data)}, 不足: {len([d for d in data if int(d[0]) < 0])}")
            
        # ========================================================
        # 22. 表示用データ取得
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
        
        # ========================================================
        # 23. 連続シフトのマージ処理
        # ========================================================
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
        
        # ========================================================
        # 24. 結果メッセージ生成と返却
        # ========================================================
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