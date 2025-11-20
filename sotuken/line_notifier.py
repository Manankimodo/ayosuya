# line_notifier.py (本番用コード)

from linebot import LineBotApi
from linebot.models import TextSendMessage

# 🚨 ここに実際の「チャンネルアクセストークン」を貼り付けてください 🚨
LINE_CHANNEL_ACCESS_TOKEN = 'rlgBIHKnI0Z1StSLVWg6h7tCQK0Xdwz+yH4MlUIy8wZaqyoNv/izM/cgd1slCDiC/rHai63OLs9bj4ACE0pV46M2oIYPwAaWADAJpIxbbcodAQIa/AyB7nbygckLrwkkxSyhmq6WBJmeam/r1nWSyQdB04t89/1O/w1cDnyilFU=' 

# APIクライアントを初期化
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)

def send_help_request_to_staff(staff_line_id, request_data, help_url, staff_name):
    """ 指定されたスタッフのLINE IDにプッシュ通知を送信する関数 """
    
    date = request_data['date']
    start = request_data['start_time']
    end = request_data['end_time']
    
    # 送信するメッセージを作成
    message_text = (
        f"🚨【緊急ヘルプ募集】🚨\n\n"
        f"スタッフの{staff_name}さん、お疲れ様です。\n"
        f"以下の日時でヘルプをお願いします。\n\n"
        f"📅 日時: {date} {start}〜{end}\n\n"
        f"入れる方は、以下のURLから【早い者勝ち】で応募してください！\n"
        f"🔗 応募URL: {help_url}"
    )
    
    try:
        # 実際にLINEサーバーへ通知を送信するコアな処理
        line_bot_api.push_message(
            to=staff_line_id, # 送信先のLINEユーザーID
            messages=TextSendMessage(text=message_text)
        )
        # コンソールにも成功ログを出力
        print(f"✅ LINE通知送信完了: ID {staff_line_id} へ (メッセージをLINEへ送信)")
        return True
    
    except Exception as e:
        # エラーが発生した場合もコンソールに出力
        print(f"❌ LINE通知送信失敗 (ID: {staff_line_id}): {e}")
        return False