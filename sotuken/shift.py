from flask import Flask, render_template, request, redirect, url_for
import pymysql
import ollama
from sentence_transformers import SentenceTransformer
import chromadb

from sotuken.app import DB_CONFIG, get_faqs

# ===== MySQL接続設定 =====
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "ayosuya",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor
}

@app.route("/manage")
def manage_faq():
    faqs = get_faqs()
    return render_template("manage_faq.html", faqs=faqs)

# 新規登録
@app.route("/add_faq", methods=["POST"])
def add_faq():
    question = request.form["question"]
    answer = request.form["answer"]
    conn = pymysql.connect(**DB_CONFIG)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO faqs (question, answer) VALUES (%s, %s)", (question, answer))
        conn.commit()
    conn.close()
    return redirect(url_for("manage_faq"))

# 編集
@app.route("/edit_faq/<int:id>", methods=["POST"])
def edit_faq(id):
    question = request.form["question"]
    answer = request.form["answer"]
    conn = pymysql.connect(**DB_CONFIG)
    with conn.cursor() as cur:
        cur.execute("UPDATE faqs SET question=%s, answer=%s WHERE id=%s", (question, answer, id))
        conn.commit()
    conn.close()
    return redirect(url_for("manage_faq"))

# 削除
@app.route("/delete_faq/<int:id>")
def delete_faq(id):
    conn = pymysql.connect(**DB_CONFIG)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM faqs WHERE id=%s", (id,))
        conn.commit()
    conn.close()
    return redirect(url_for("manage_faq"))