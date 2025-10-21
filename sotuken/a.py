from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import text
from extensions import db  # ✅ extensions から import

login_bp = Blueprint('login', __name__, url_prefix='/login')

# -----------------------
# 🔹 ログイン処理
# -----------------------
@login_bp.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form['user_id']
        password = request.form['password']

        sql = text("SELECT * FROM account WHERE ID = :user_id AND password = :password")
        result = db.session.execute(sql, {'user_id': user_id, 'password': password}).fetchone()

        if result:
            session['user_id'] = user_id
            return redirect(url_for('login.check'))  # ✅ Blueprint名.login関数名
        else:
            flash('IDまたはパスワードが違います', 'danger')

    return render_template('login.html')


@login_bp.route('/check')
def check():
    if "user_id" not in session:
        return redirect(url_for('login.login'))
    return render_template("check.html")

@login_bp.route('/admin')
def admin():
    return render_template("calendar2.html")

@login_bp.route('/shift')
def shift():
    return render_template("login.html")

@login_bp.route("/logout")
def logout():
    session.pop("user", None)
    flash("ログアウトしました。", "info")
    return redirect(url_for("login"))

