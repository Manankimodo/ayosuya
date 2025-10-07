from flask import Flask, render_template, request, redirect, url_for
from flask_mysqldb import MySQL

app = Flask(__name__)

# XAMPPのMySQL接続設定
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''  # XAMPPは通常パスワードなし
app.config['MYSQL_DB'] = 'ayosuya'  # ← あなたのデータベース名に変更

mysql = MySQL(app)

# カレンダー表示
@app.route("/")
def calendar():
    return render_template("calendar.html")

# 申請フォーム
@app.route("/sinsei/<date>", methods=["GET", "POST"])
def sinsei(date):
    if request.method == "POST":
        name = request.form["name"]
        work = request.form["work"]
        time = request.form["time"]
        start_time, end_time = time.split("~")

        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO schedule (ID, date, work, start_time, end_time) VALUES (%s, %s, %s, %s, %s)",
            (name, date, work, start_time, end_time)
        )
        mysql.connection.commit()
        cur.close()

        return redirect(url_for("calendar"))

    return render_template("sinsei.html", date=date)

if __name__ == "__main__":
    app.run(debug=True)
