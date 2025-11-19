# line_notifier.py (Flaskのインポートは無し)

def send_help_request_to_staff(staff_line_id, request_data, help_url):
    """ 指定されたスタッフのLINE IDに急募メッセージを送信する関数 (シミュレーション) """
    
    date = request_data['date']
    start = request_data['start_time']
    end = request_data['end_time']
    
    print(f"--- LINE Bot通知シミュレーション ---")
    print(f"宛先LINE ID: {staff_line_id}")
    print(f"日時: {date} {start}〜{end}")
    print("-----------------------------------")
    
    return True