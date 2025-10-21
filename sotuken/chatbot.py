# faq.py
from flask import Blueprint, render_template, request
import pymysql
import ollama
from sentence_transformers import SentenceTransformer
import chromadb

# ===== Flask Blueprint設定 =====
faq_bp = Blueprint('faq', __name__, url_prefix='/faq')

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

# ===== /ask エンドポイント =====
@faq_bp.route("/ask", methods=["POST"])
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
