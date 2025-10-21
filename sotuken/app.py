# from flask import Flask, render_template, request, redirect, url_for
# from flask_mysqldb import MySQL
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from sentence_transformers import SentenceTransformer
import chromadb
import ollama
import warnings



#--------------------------------------------------------------------------------

# 警告を非表示
warnings.filterwarnings("ignore")
app = Flask(__name__)
app.secret_key = "your_secret_key"  # ← セッションに必須（任意の文字列でOK）



# ==========================
# 🔹 1. MariaDB接続設定
# ==========================
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'mysql+pymysql://root:@localhost/ayosuya?unix_socket=/Applications/XAMPP/xamppfiles/var/mysql/mysql.sock'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
# mysql = MySQL(app)


# 仮のユーザーデータ
users = {
    "user1": {"password": "1234"},
    "admin": {"password": "adminpass"}
}

@app.route("/check")
def check():
    # ログイン済み確認
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("check.html")

@app.route("/admin")
def admin():
    return render_template ("calendar.html")

@app.route("/shift")
def shift():
    return render_template ("login.html")


# カレンダー表示

# ==========================
# 🔹 2. Chroma + AI設定
# ==========================
embedder = SentenceTransformer("all-MiniLM-L6-v2")#文章を数値ベクトルに変換

chroma_client = chromadb.PersistentClient(path="./chroma_db")#類似度検索
collection = chroma_client.get_or_create_collection("faq_collection")#コレクションを作って保存

faqs = [
    {"q": "シフトはどうやって提出しますか？", "a": "シフト希望は毎週日曜までにLINEで提出してください。"},
    {"q": "新人研修はどのくらいですか？", "a": "新人研修は約3日間行います。"},
    {"q": "有給はいつ使えますか？", "a": "有給は入社6ヶ月後から取得可能です。"}
]


#各質問をSentenceTransformerで**埋め込み（ベクトル化）**してChromaに保存。
for i, faq in enumerate(faqs):
    if not collection.get(ids=[str(i)])["ids"]:  # 未登録なら
        embedding = embedder.encode(faq["q"]).tolist()
        collection.add(
            ids=[str(i)],
            embeddings=[embedding],
            metadatas=[{"answer": faq["a"]}],
            documents=[faq["q"]]
        )


# @app.route("/")
# def index():


# ==========================
# 🔹 3. ルート（共通UI）
# ==========================

#トップページ (/) にアクセスしたとき、index.html を表示。
@app.route("/")
def index():
    return render_template("login.html")


# ==========================
# 🔹 4. ログイン機能追加
# ==========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_id = request.form["user_id"]
        password = request.form["password"]

        sql = text("SELECT * FROM account WHERE ID = :user_id AND password = :password")
        result = db.session.execute(sql, {"user_id": user_id, "password": password}).fetchone()

        if result:
            session["user_id"] = user_id
            return redirect(url_for("check"))
        else:
            flash("IDまたはパスワードが間違っています。", "danger")
    
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("ログアウトしました。", "info")
    return redirect(url_for("login"))


# ==========================
# 🔹 4. チャットボット機能
# ==========================

# １フォームから送られた質問を取得。
# ２SentenceTransformer で埋め込みベクトルに変換。
# ３ChromaDBから類似度が高いFAQを2件検索。
# ４その結果を元に「コンテキスト（参考情報）」を作成。

@app.route("/ask", methods=["POST"])
def ask():
    user_question = request.form["question"]

    # 類似FAQ検索
    query_emb = embedder.encode(user_question).tolist()
    results = collection.query(query_embeddings=[query_emb], n_results=2)

    # コンテキスト生成
    context = "\n".join([
        f"Q: {d}\nA: {m['answer']}"
        for d, m in zip(results["documents"][0], results["metadatas"][0])
    ])

    prompt = f"""
以下はFAQです。ユーザーの質問に答えてください。

{context}

ユーザーの質問: {user_question}
"""

    #Ollama（mistral モデル）に「FAQ＋ユーザー質問」を渡して回答を生成。
    response = ollama.chat(model="mistral", messages=[{"role": "user", "content": prompt}])
    answer = response["message"]["content"]


    #結果（質問と回答）を index.html に渡して再表示。
    return render_template("index.html", question=user_question, answer=answer)

# ==========================
# 🔹 5. カレンダー表示
# ==========================
@app.route("/calendar")
def calendar():
    return render_template("calendar.html")


# ==========================
# 🔹 6. 希望申請フォーム
# ==========================
@app.route("/sinsei/<date>", methods=["GET", "POST"])
def sinsei(date):
    if request.method == "POST":
        name = request.form.get("name")
        work = request.form.get("work")
        time = request.form.get("time")

        # 時間フォーマット変換
        if "~" in time:
            start_time, end_time = time.split("~")
            start_time = start_time.strip() + ":00"
            end_time = end_time.strip() + ":00"
        else:
            start_time = None
            end_time = None

        # SQLでINSERT
        sql = text("""
            INSERT INTO calendar (ID, date, work, start_time, end_time)
            VALUES (:name, :date, :work, :start_time, :end_time)
        """)

        db.session.execute(sql, {
            "name": name,
            "date": date,
            "work": work,
            "start_time": start_time,
            "end_time": end_time
        })
        db.session.commit()

        return redirect(url_for("calendar"))

    return render_template("sinsei.html", date=date)


# ==========================
# 🔹 メイン
# ==========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
