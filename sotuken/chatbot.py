# chatbot.py
from flask import Blueprint, render_template, request
from sentence_transformers import SentenceTransformer
import chromadb
import ollama

chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/chatbot")

# --- AIセットアップ ---
embedder = SentenceTransformer("all-MiniLM-L6-v2")
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection("faq_collection")

# チャット画面ではDB更新はせず、Chromaにあるデータだけ検索
@chatbot_bp.route("/", methods=["GET", "POST"])
def chat():
    if request.method == "POST":
        user_question = request.form["question"]

        # 類似検索
        query_emb = embedder.encode(user_question).tolist()
        results = collection.query(query_embeddings=[query_emb], n_results=2)

        # FAQが一件もない場合
        if not results["documents"] or len(results["documents"][0]) == 0:
            return render_template("index.html", question=user_question, answer="FAQがまだ登録されていません。")

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

        return render_template("index.html", question=user_question, answer=answer)

    return render_template("index.html")
