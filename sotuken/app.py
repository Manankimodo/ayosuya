from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

# データベース初期化
def init_db():
    conn = sqlite3.connect("schedule.db")
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS hopes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            date TEXT,
            work TEXT,
            time TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# カレンダー画面
@app.route('/')
def calendar():
    return render_template('calendar.html')

# 日付選択後の入力画面
@app.route('/select/<date>', methods=['GET', 'POST'])
def select(date):
    if request.method == 'POST':
        name = request.form['name']
        work = request.form['work']
        time = request.form['time']

        conn = sqlite3.connect("schedule.db")
        cur = conn.cursor()
        cur.execute("INSERT INTO hopes (name, date, work, time) VALUES (?, ?, ?, ?)",
                    (name, date, work, time))
        conn.commit()
        conn.close()

        return redirect(url_for('confirm', name=name))

    return render_template('schedule_form.html', date=date)

# 確認画面
@app.route('/confirm/<name>')
def confirm(name):
    conn = sqlite3.connect("schedule.db")
    cur = conn.cursor()
    cur.execute("SELECT date, work, time FROM hopes WHERE name = ?", (name,))
    data = cur.fetchall()
    conn.close()
    return render_template('confirm.html', name=name, data=data)

if __name__ == '__main__':
    app.run(debug=True)
