from flask import Flask, render_template, request, redirect, url_for
import pymysql
import ollama
from sentence_transformers import SentenceTransformer
import chromadb

app = Flask(__name__)

# ===== Embedding & Chroma設定 =====
embedder = SentenceTransformer("all-MiniLM-L6-v2")
chroma_client = chromadb.Client()
collection = chroma_client.get_or_create_collection("faq_collection")

# ===== MySQL接続設定 =====
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "ayosuya",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor
}


# ===== FAQ取得関数 =====
def get_faqs():
    conn = pymysql.connect(**DB_CONFIG)
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM faqs")
        data = cur.fetchall()
    conn.close()
    return data

# ===== Chroma更新関数 =====
def update_chroma_from_db():
    faqs = get_faqs()

    # 既存データを全削除
    existing = collection.get()
    if len(existing["ids"]) > 0:
        collection.delete(ids=existing["ids"])

    # DBから再登録
    for faq in faqs:
        emb = embedder.encode(faq["question"]).tolist()
        collection.add(
            ids=[str(faq["id"])],
            embeddings=[emb],
            documents=[faq["question"]],
            metadatas=[{"answer": faq["answer"]}]
        )


# ===== チャット画面 =====
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    update_chroma_from_db()  # 毎回FAQを最新化
    user_question = request.form["question"]

    query_emb = embedder.encode(user_question).tolist()
    results = collection.query(query_embeddings=[query_emb], n_results=2)

    context = "\n".join([
        f"Q: {d}\nA: {m['answer']}"
        for d, m in zip(results["documents"][0], results["metadatas"][0])
    ])

    prompt = f"""
以下はFAQです。ユーザーの質問に答えてください。

{context}

ユーザーの質問: {user_question}
"""

    response = ollama.chat(model="mistral", messages=[{"role": "user", "content": prompt}])
    answer = response["message"]["content"]

    return render_template("index.html", question=user_question, answer=answer)


# ===== FAQ管理画面 =====
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
