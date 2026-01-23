# ==========================================
# 4.8曜日タイプ別の需要リセット処理(新規追加)
# ==========================================
@makeshift_bp.route("/settings/demand/reset_by_type", methods=["POST"])
def reset_demand_by_type():
    # ログイン確認
    if "user_id" not in session:
        flash("ログインが必要です", "danger")
        return redirect(url_for("login.login"))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # store_id取得
        user_id = session["user_id"]
        cursor.execute("SELECT store_id FROM account WHERE ID = %s", (user_id,))
        user_data = cursor.fetchone()
        store_id = user_data["store_id"] if user_data else None
        
        if not store_id:
            flash("❌ 店舗情報が紐付いていません。", "danger")
            return redirect(url_for("makeshift.settings"))
        
        day_type = request.form.get("day_type", "weekday")
        
        # day_typeで絞り込んで削除
        cursor.execute("""
            DELETE FROM shift_demand 
            WHERE store_id = %s AND day_type = %s
        """, (store_id, day_type))
        
        conn.commit()
        day_type_label = "平日" if day_type == "weekday" else "土日祝"
        flash(f"🗑 {day_type_label}の設定をリセットしました", "warning")
        
    except Exception as e:
        conn.rollback()
        print(f"Reset By Type Error: {e}")
        
    finally:
        conn.close()
        
    return redirect(url_for('makeshift.settings') + '#demand-section')



# ==========================================
# 4. 需要をリセット(全削除)する処理
# ==========================================
@makeshift_bp.route("/settings/demand/reset", methods=["POST"])
def reset_demand():
    # ログイン確認
    if "user_id" not in session:
        flash("ログインが必要です", "danger")
        return redirect(url_for("login.login"))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # store_id取得
        user_id = session["user_id"]
        cursor.execute("SELECT store_id FROM account WHERE ID = %s", (user_id,))
        user_data = cursor.fetchone()
        store_id = user_data["store_id"] if user_data else None
        
        if not store_id:
            flash("❌ 店舗情報が紐付いていません。", "danger")
            return redirect(url_for("makeshift.settings"))
        
        # store_idで絞り込み
        cursor.execute("DELETE FROM shift_demand WHERE store_id = %s", (store_id,))
        conn.commit()
        flash("🗑 設定をすべてリセットしました", "warning")
        
    except Exception as e:
        conn.rollback()
        print(f"Reset Error: {e}")
        
    finally:
        conn.close()
        
    return redirect(url_for('makeshift.settings'))