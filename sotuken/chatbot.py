from flask import Blueprint, render_template, request
from sentence_transformers import SentenceTransformer
import chromadb
import ollama
from extensions import db

faq_bp = Blueprint("faq", __name__, url_prefix="/faq")

# --- AIセットアップ ---
embedder = SentenceTransformer("all-MiniLM-L6-v2")
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection("faq_collection")

faqs = [
    {"q": "シフトはどうやって提出しますか？", "a": "シフト希望は毎週日曜までにLINEで提出してください。"},
    {"q": "新人研修はどのくらいですか？", "a": "新人研修は約3日間行います。"},
    {"q": "有給はいつ使えますか？", "a": "有給は入社6ヶ月後から取得可能です。"}
]

for i, faq in enumerate(faqs):
    if not collection.get(ids=[str(i)])["ids"]:
        embedding = embedder.encode(faq["q"]).tolist()
        collection.add(
            ids=[str(i)],
            embeddings=[embedding],
            metadatas=[{"answer": faq["a"]}],
            documents=[faq["q"]]
        )

@faq_bp.route("/", methods=["GET", "POST"])
def faq():
    if request.method == "POST":
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

    return render_template("index.html")
