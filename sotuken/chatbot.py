# chatbot.py
from flask import Blueprint, render_template, request, session
from sentence_transformers import SentenceTransformer
import chromadb
import ollama

chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/chatbot")

# --- AIセットアップ ---
embedder = SentenceTransformer("all-MiniLM-L6-v2")
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection("faq_collection")

@chatbot_bp.route("/", methods=["GET", "POST"])
def chat():
    # --- セッションにチャット履歴を保持 ---
    if "chat_history" not in session:
        session["chat_history"] = []

    if request.method == "POST":
        user_question = request.form["question"]

        # 類似検索
        query_emb = embedder.encode(user_question).tolist()
        results = collection.query(query_embeddings=[query_emb], n_results=2)

        if not results["documents"] or len(results["documents"][0]) == 0:
            answer = "FAQがまだ登録されていません。"
        else:
            # コンテキスト生成
            context = "\n".join([
                f"Q: {d}\nA: {m['answer']}"
                for d, m in zip(results["documents"][0], results["metadatas"][0])
            ])

            # Ollamaで回答生成
            prompt = f"""
以下はFAQです。ユーザーの質問に最も関連する回答を出してください。

{context}

ユーザーの質問: {user_question}
"""
            response = ollama.chat(model="mistral", messages=[{"role": "user", "content": prompt}])
            answer = response["message"]["content"]

        # 履歴に追加
        session["chat_history"].append({"role": "user", "text": user_question})
        session["chat_history"].append({"role": "bot", "text": answer})
        session.modified = True  # ← セッション更新を明示

    # 最新の履歴を表示
    chat_history = session.get("chat_history", [])
    return render_template("index.html", chat_history=chat_history)
