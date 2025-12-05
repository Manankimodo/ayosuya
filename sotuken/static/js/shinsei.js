function toggleTimeInputs() {
    const workSelect = document.querySelector('select[name="work"]');
    const startTime = document.querySelector('input[name="start_time"]');
    const endTime = document.querySelector('input[name="end_time"]');
    
    if (workSelect.value === "0") {
        // 出勤不可なら時間入力を無効化＆値をクリア
        startTime.disabled = true;
        endTime.disabled = true;
        startTime.value = "";
        endTime.value = "";
    } else {
        // 出勤可能なら時間入力を有効化
        startTime.disabled = false;
        endTime.disabled = false;
    }
}

// ページ読み込み時にも反映
window.onload = toggleTimeInputs;

    function validateForm() {
        const workSelect = document.getElementById('workSelect');
        // 「出勤不可」の場合はチェック不要
        if (workSelect.value === "0") {
            return true;
        }

        const startInput = document.getElementById('startTime').value;
        const endInput = document.getElementById('endTime').value;
        
        if (!startInput || !endInput) {
            alert("開始時間と終了時間を入力してください。");
            return false;
        }

        // 時間計算のための日付オブジェクト作成 (日付は今日で固定)
        const baseDate = "2000-01-01";
        const startDate = new Date(`${baseDate}T${startInput}`);
        let endDate = new Date(`${baseDate}T${endInput}`);

        // 日付またぎの対応 (例: 23:00 〜 02:00)
        if (endDate <= startDate) {
            endDate.setDate(endDate.getDate() + 1);
        }

        // 差分を計算 (ミリ秒 -> 時間)
        const diffMs = endDate - startDate;
        const diffHours = diffMs / (1000 * 60 * 60);

        // 設定値を取得
        const settingsDiv = document.getElementById('shift-settings');
        const minHours = parseFloat(settingsDiv.dataset.minHours) || 0;

        // チェック！
        if (diffHours < minHours) {
            alert(`⚠️ エラー：勤務時間が短すぎます。\n\n最低でも 【 ${minHours}時間 】 以上のシフトを入力してください。\n(現在の入力: ${diffHours.toFixed(1)}時間)`);
            return false; // 送信をキャンセル
        }

        return true; // OKなら送信
    }

    // 既存の toggleTimeInputs もここにあると仮定して、
    // もし shinsei.js にあるならそのままでOKですが、念のため
    function toggleTimeInputs() {
        const val = document.getElementById('workSelect').value;
        const st = document.getElementById('startTime');
        const et = document.getElementById('endTime');
        if (val === "0") {
            st.disabled = true; st.required = false; st.value = "";
            et.disabled = true; et.required = false; et.value = "";
        } else {
            st.disabled = false; st.required = true;
            et.disabled = false; et.required = true;
        }
    }
