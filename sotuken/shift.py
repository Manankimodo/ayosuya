from flask import Blueprint, render_template, redirect, url_for, session, request
from sqlalchemy import text
from extensions import db
import chromadb
from sentence_transformers import SentenceTransformer

shift_bp = Blueprint("shift", __name__, url_prefix="/shift")

# ==========================
# 🔹 Chroma初期設定
# ==========================
embedder = SentenceTransformer("all-MiniLM-L6-v2")
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection("faq_collection")


def rebuild_chroma_from_db():
    """DB内のFAQをもとにChromaを再構築"""
    # 一度全削除
    all_ids = collection.get()["ids"]
    if all_ids:  # IDがある場合のみ削除
        collection.delete(ids=all_ids)

    # DBから全FAQ取得
    faqs = db.session.execute(text("SELECT id, question, answer FROM faqs")).fetchall()

    for faq in faqs:
        embedding = embedder.encode(faq.question).tolist()
        collection.add(
            ids=[str(faq.id)],
            embeddings=[embedding],
            metadatas=[{"answer": faq.answer}],
            documents=[faq.question]
        )
    print("✅ ChromaをDBの内容で更新しました")



# ==========================
# 🔹 FAQ管理画面
# ==========================
@shift_bp.route("/manage")
def manage_faq():
    faqs = db.session.execute(text("SELECT * FROM faqs")).fetchall()
    return render_template("manage_faq.html", faqs=faqs)


# ==========================
# 🔹 FAQ追加
# ==========================
@shift_bp.route("/add_faq", methods=["POST"])
def add_faq():
    question = request.form["question"]
    answer = request.form["answer"]

    # DB登録
    db.session.execute(
        text("INSERT INTO faqs (question, answer) VALUES (:q, :a)"),
        {"q": question, "a": answer}
    )
    db.session.commit()

    # Chromaに追加
    # 登録したFAQのIDを取得
    faq_id = db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    embedding = embedder.encode(question).tolist()
    collection.add(
        ids=[str(faq_id)],
        embeddings=[embedding],
        documents=[question],
        metadatas=[{"answer": answer}]
    )

    return redirect(url_for("shift.manage_faq"))



# ==========================
# 🔹 FAQ編集
# ==========================
@shift_bp.route("/edit_faq/<int:id>", methods=["POST"])
def edit_faq(id):
    question = request.form["question"]
    answer = request.form["answer"]

    # DB更新
    db.session.execute(
        text("UPDATE faqs SET question=:q, answer=:a WHERE id=:id"),
        {"q": question, "a": answer, "id": id}
    )
    db.session.commit()

    # Chroma更新（既存のidを削除して追加）
    collection.delete(ids=[str(id)])
    embedding = embedder.encode(question).tolist()
    collection.add(
        ids=[str(id)],
        embeddings=[embedding],
        documents=[question],
        metadatas=[{"answer": answer}]
    )

    return redirect(url_for("shift.manage_faq"))


# ==========================
# 🔹 FAQ削除
# ==========================
@shift_bp.route("/delete_faq/<int:id>")
def delete_faq(id):
    # DB削除
    db.session.execute(text("DELETE FROM faqs WHERE id=:id"), {"id": id})
    db.session.commit()

    # Chromaから削除
    collection.delete(ids=[str(id)])

    return redirect(url_for("shift.manage_faq"))
