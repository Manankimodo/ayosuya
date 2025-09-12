from flask import Flask, render_template, request
from sentence_transformers import SentenceTransformer
import chromadb
import ollama
import warnings

# 警告は無視
warnings.filterwarnings("ignore")

app = Flask(__name__)

# 1. 埋め込みモデル準備
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# 2. Chroma クライアント作成
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection("faq_collection")

# 3. FAQデータ登録（最初に1回だけ）
faqs = [
    {"q": "シフトはどうやって提出しますか？", "a": "シフト希望は毎週日曜までにLINEで提出してください。"},
    {"q": "新人研修はどのくらいですか？", "a": "新人研修は約3日間行います。"},
    {"q": "有給はいつ使えますか？", "a": "有給は入社6ヶ月後から取得可能です。"}
]


for i, faq in enumerate(faqs):
    if not collection.get(ids=[str(i)])["ids"]:  # 未登録なら
        embedding = embedder.encode(faq["q"]).tolist()
        collection.add(
            ids=[str(i)],
            embeddings=[embedding],
            metadatas=[{"answer": faq["a"]}],
            documents=[faq["q"]]
        )

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    user_question = request.form["question"]

    # 4. Chromaで類似FAQ検索
    query_emb = embedder.encode(user_question).tolist()
    results = collection.query(query_embeddings=[query_emb], n_results=2)

    # 5. コンテキスト作成
    context = "\n".join([f"Q: {d}\nA: {m['answer']}"
                        for d, m in zip(results['documents'][0], results['metadatas'][0])])

    prompt = f"""
以下はFAQです。ユーザーの質問に答えてください。

{context}

ユーザーの質問: {user_question}
"""

    # 6. Ollama(Mistral)に投げて回答生成
    response = ollama.chat(model="mistral", messages=[{"role": "user", "content": prompt}])
    answer = response["message"]["content"]

    return render_template("index.html", question=user_question, answer=answer)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
