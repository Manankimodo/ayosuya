from flask import Blueprint, render_template, request, session, jsonify
from sentence_transformers import SentenceTransformer
import ollama
from extensions import db
from sqlalchemy import text as sql_text
 
chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/chatbot")
 
# --- AI設定 ---
embedder = SentenceTransformer("all-MiniLM-L6-v2")
# --- 応答キャッシュ ---
answer_cache = {}
 
# ===========================
# ヘルパー関数：ユーザー名を取得
# ===========================
def get_user_name():
    """セッションからユーザー名（文字列）を取得"""
    user_info = session.get("user", {})
    if isinstance(user_info, dict):
        return str(user_info.get("name", "guest"))
    return "guest"
 
# ===========================
# ヘルパー関数：ユーザー名を取得
# ===========================
def get_user_name():
    """セッションからユーザー名（文字列）を取得"""
    user_info = session.get("user", {})
    if isinstance(user_info, dict):
        return str(user_info.get("name", "guest"))
    return "guest"

# ===========================
# DB操作ヘルパー
# ===========================
def save_chat(user_name, role, content):
    user_name = str(user_name)
    db.session.execute(
        sql_text("INSERT INTO chat_history (user_name, role, text) VALUES (:u, :r, :t)"),
        {"u": user_name, "r": role, "t": content}
    )
    db.session.commit()
 
def load_chat(user_name):
    user_name = str(user_name)
    rows = db.session.execute(
        sql_text("SELECT role, text FROM chat_history WHERE user_name=:u ORDER BY created_at ASC"),
        {"u": user_name}
    ).fetchall()
    return [{"role": r.role, "text": r.text} for r in rows]
def get_all_faqs():
    """FAQテーブルから全てのQ&Aを取得"""
    rows = db.session.execute(
        sql_text("SELECT id, question, answer FROM faqs")
    ).fetchall()
    return [{"id": r.id, "question": r.question, "answer": r.answer} for r in rows]
# ===========================
# チャット画面
# ===========================
@chatbot_bp.route("/", methods=["GET", "POST"])
def chat():
    user_name = get_user_name()
    chat_history = load_chat(user_name)
 
    if request.method == "POST":
        user_question = request.form["question"]
 
        # キャッシュを確認
        if user_question in answer_cache:
            answer = answer_cache[user_question]
        else:
            answer = generate_answer(user_question)
            answer_cache[user_question] = answer
 
        # 履歴保存
        save_chat(user_name, "user", user_question)
        save_chat(user_name, "bot", answer)
 
        chat_history.append({"role": "user", "text": user_question})
        chat_history.append({"role": "bot", "text": answer})
 
    return render_template("index.html", chat_history=chat_history)
 
# ===========================
# 回答再生成（Ajax用）
# ===========================
@chatbot_bp.route("/regenerate", methods=["POST"])
def regenerate():
    user_name = get_user_name()
    user_question = request.form["question"]
 
    # キャッシュを無視して再生成
    answer = generate_answer(user_question)
 
    # 保存
    save_chat(user_name, "bot", answer)
    answer_cache[user_question] = answer
 
    return jsonify({"answer": answer})
 
# ===========================
# 共通：回答生成関数（Ollama + MySQLのFAQ使用）
# ===========================
def generate_answer(user_question):
    try:
        # データベースから全FAQを取得
        faqs = get_all_faqs()
        
        if not faqs:
            return "FAQがまだ登録されていません。"
        # 質問の埋め込みベクトルを作成
        query_emb = embedder.encode(user_question)
        
        # 各FAQの質問と類似度を計算
        similarities = []
        for faq in faqs:
            faq_emb = embedder.encode(faq["question"])
            # コサイン類似度を計算
            similarity = sum(query_emb * faq_emb) / (
                (sum(query_emb ** 2) ** 0.5) * (sum(faq_emb ** 2) ** 0.5)
            )
            similarities.append((similarity, faq))
        
        # 類似度が高い順にソート
        similarities.sort(reverse=True, key=lambda x: x[0])
        
        # 上位2件を取得
        top_faqs = similarities[:2]
        
        # コンテキストを作成
        context = "\n".join([
            f"Q: {faq['question']}\nA: {faq['answer']}"
            for _, faq in top_faqs
        ])

        prompt = f"""
以下はFAQです。ユーザーの質問に最も関連する回答を、FAQの内容を参考にして日本語で答えてください。

{context}
 
ユーザーの質問: {user_question}
"""
        # Ollama APIで回答生成
        response = ollama.chat(model="mistral", messages=[{"role": "user", "content": prompt}])
        return response["message"]["content"]
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return "申し訳ございません。回答の生成中にエラーが発生しました。"
# ===========================
# 履歴削除
# ===========================
@chatbot_bp.route("/clear", methods=["POST"])
def clear_history():
    user_name = get_user_name()
    db.session.execute(sql_text("DELETE FROM chat_history WHERE user_name=:u"), {"u": user_name})
    db.session.commit()
    answer_cache.clear()
    return "", 204
 
 