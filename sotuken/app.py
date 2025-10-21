# app.py
from flask import Flask, redirect, url_for
from extensions import db  # ✅ ← dbをこちらからimport

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# --- DB設定 ---
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'mysql+pymysql://root:@localhost/ayosuya?unix_socket=/Applications/XAMPP/xamppfiles/var/mysql/mysql.sock'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- DB初期化 ---
db.init_app(app)

# --- Blueprintの読み込み ---
from a import login_bp
from calendar_page import calendar_bp
from insert import insert_bp
from chatbot import faq_bp
from shift import shift_bp

# --- Blueprint登録 ---
app.register_blueprint(login_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(insert_bp)
app.register_blueprint(faq_bp)
app.register_blueprint(shift_bp)



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

    # DBから再登録
    for faq in faqs:
        emb = embedder.encode(faq["question"]).tolist()

        collection.add(
            ids=[str(faq["id"])],
            embeddings=[emb],
            documents=[faq["question"]],
            metadatas=[{"answer": faq["answer"]}]
        )



# @app.route("/")
# def index():


# ==========================
# 🔹 3. ルート（共通UI）
# ==========================


# ===== チャット画面 =====
@app.route("/")

# --- トップページ（ルート） ---

# -------------------------------------------------
# 🔹 トップページ（ルート）
# -------------------------------------------------

@app.route('/')

def index():
    return redirect(url_for('login.login'))

if __name__ == '__main__':
    app.run(debug=True)
