# line_bot.py (BlueprintとFlask関連のみ)
from flask import Blueprint 

# 🚨 line_bot_bp の定義はここに残します
line_bot_bp = Blueprint("line_bot", __name__, url_prefix="/line_bot")

# 🚨 他のルート定義（例: Webhook）もここに追加

# 例: 
# @line_bot_bp.route("/webhook", methods=["POST"])
# def webhook():
#     # ... 処理 ...
#     pass