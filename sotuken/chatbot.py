from flask import Blueprint, render_template, request, session
from sentence_transformers import SentenceTransformer
import chromadb
import ollama
from extensions import db
from sqlalchemy import text as sql_text  # text と被らないように別名で import

chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/chatbot")

# --- AI設定 ---
embedder = SentenceTransformer("all-MiniLM-L6-v2")
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection("faq_collection")

# --- Ollama応答キャッシュ（同じ質問で再生成を避ける） ---
answer_cache = {}

# ===========================
# DB操作ヘルパー
# ===========================
def save_chat(user_name, role, content):
    db.session.execute(
        sql_text("INSERT INTO chat_history (user_name, role, text) VALUES (:u, :r, :t)"),
        {"u": user_name, "r": role, "t": content}
    )
    db.session.commit()

def load_chat(user_name):
    rows = db.session.execute(
        sql_text("SELECT role, text FROM chat_history WHERE user_name=:u ORDER BY created_at ASC"),
        {"u": user_name}
    ).fetchall()
    return [{"role": r.role, "text": r.text} for r in rows]

# ===========================
# チャット画面
# ===========================
@chatbot_bp.route("/", methods=["GET", "POST"])
def chat():
    user_name = session.get("user", "guest")
    chat_history = load_chat(user_name)

    if request.method == "POST":
        user_question = request.form["question"]

        if user_question in answer_cache:
            answer = answer_cache[user_question]
        else:
            query_emb = embedder.encode(user_question).tolist()
            results = collection.query(query_embeddings=[query_emb], n_results=2)

            if not results["documents"] or len(results["documents"][0]) == 0:
                answer = "FAQがまだ登録されていません。"
            else:
                context = "\n".join([
                    f"Q: {d}\nA: {m['answer']}"
                    for d, m in zip(results["documents"][0], results["metadatas"][0])
                ])
                prompt = f"""
以下はFAQです。ユーザーの質問に最も関連する回答を出してください。

{context}

ユーザーの質問: {user_question}
"""
                response = ollama.chat(model="mistral", messages=[{"role": "user", "content": prompt}])
                answer = response["message"]["content"]
                answer_cache[user_question] = answer

        save_chat(user_name, "user", user_question)
        save_chat(user_name, "bot", answer)

        chat_history.append({"role": "user", "text": user_question})

        # chat_history.append({"role": "bot", "text": answer})

    return render_template("index.html", chat_history=chat_history)

# ===========================
# チャット履歴削除
# ===========================
@chatbot_bp.route("/clear", methods=["POST"])
def clear_history():
    user_name = session.get("user", "guest")
    db.session.execute(
        sql_text("DELETE FROM chat_history WHERE user_name=:u"),
        {"u": user_name}
    )
    db.session.commit()
    answer_cache.clear()
    return "", 204