from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)

# ✅ XAMPP（MariaDB）への接続設定
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'mysql+pymysql://root:@localhost/ayosuya?unix_socket=/Applications/XAMPP/xamppfiles/var/mysql/mysql.sock'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ✅ カレンダー表示
@app.route("/")
def calendar():
    return render_template("calendar.html")


# ✅ 希望申請フォーム
@app.route("/sinsei/<date>", methods=["GET", "POST"])
def sinsei(date):
    if request.method == "POST":
        name = request.form.get("name")
        work = request.form.get("work")
        time = request.form.get("time")

        # "9:00~13:00" → ("9:00", "13:00")
        if "~" in time:
            start_time, end_time = time.split("~")
            start_time = start_time.strip() + ":00"
            end_time = end_time.strip() + ":00"
        else:
            start_time = None
            end_time = None

        # ✅ SQLAlchemyのtext()で安全にINSERT
        sql = text("""
            INSERT INTO calendar (ID, date, work, start_time, end_time)
            VALUES (:name, :date, :work, :start_time, :end_time)
        """)

        # ✅ パラメータを渡して実行
        db.session.execute(sql, {
            "name": name,
            "date": date,
            "work": work,
            "start_time": start_time,
            "end_time": end_time
        })
        db.session.commit()

        return redirect(url_for("calendar"))

    return render_template("sinsei.html", date=date)


if __name__ == "__main__":
    app.run(debug=True)
