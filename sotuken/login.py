from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import text
from extensions import db

login_bp = Blueprint('login', __name__, url_prefix='/login')

@login_bp.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_id = request.form.get('login_id')
        password = request.form.get('password')

        # ============================
        # ① 店長ログイン（store_code）
        # ============================
        sql_manager = text("""
            SELECT a.*, s.store_code
            FROM account a
            JOIN store s ON a.store_id = s.id
            WHERE s.store_code = :code AND a.password = :password
        """)

        manager = db.session.execute(
            sql_manager,
            {"code": login_id, "password": password}
        ).fetchone()

        if manager:
            session['user_id'] = manager.id
            session['role'] = manager.role  # manager
            return redirect(url_for("login.manager_home"))

        # ============================
        # ② 従業員ログイン（ID）
        # ============================
        sql_staff = text("""
            SELECT *
            FROM account
            WHERE id = :id AND password = :password
        """)

        staff = db.session.execute(
            sql_staff,
            {"id": login_id, "password": password}
        ).fetchone()

        if staff:
            session['user_id'] = staff.id
            session['role'] = staff.role  # staff
            return redirect(url_for("login.staff_home"))

        # ============================
        # ログイン失敗
        # ============================
        flash("ログインID または パスワードが間違っています", "danger")

    return render_template("login.html")

@login_bp.route('/manager/home')
def manager_home():
    if session.get("role") != "manager":
        return redirect(url_for("login.login"))
    return render_template("calendar2.html")  # 店長画面


@login_bp.route('/staff/home')
def staff_home():
    if session.get("role") != "staff":
        return redirect(url_for("login.login"))
    return render_template("calendar.html")  # 従業員画面
