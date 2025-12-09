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


        // バリデーション関数
    function validateForm() {
      const workSelect = document.getElementById('workSelect');
      const startTime = document.getElementById('startTime').value;
      const endTime = document.getElementById('endTime').value;
      
      // 出勤不可の場合はチェック不要
      if (workSelect.value === '0') {
        return true;
      }
      
      if (!startTime || !endTime) {
        alert('開始時間と終了時間を入力してください。');
        return false;
      }
      
      const settings = document.getElementById('shift-settings');
      const minHours = parseFloat(settings.dataset.minHours);
      const startLimit = settings.dataset.startLimit;
      const endLimit = settings.dataset.endLimit;
      
      // ★★★ 時刻を分単位に変換して比較 ★★★
      function timeToMinutes(timeStr) {
        const [hours, minutes] = timeStr.split(':').map(Number);
        return hours * 60 + minutes;
      }
      
      const startMinutes = timeToMinutes(startTime);
      const endMinutes = timeToMinutes(endTime);
      const startLimitMinutes = timeToMinutes(startLimit);
      const endLimitMinutes = timeToMinutes(endLimit);
      
      // 時間差を計算
      const start = new Date(`2000-01-01T${startTime}:00`);
      const end = new Date(`2000-01-01T${endTime}:00`);
      
      let diffHours = (end - start) / (1000 * 60 * 60);
      
      // 日付をまたぐ場合の処理
      if (diffHours < 0) {
        diffHours += 24;
      }
      
      // 最低勤務時間チェック
      if (diffHours < minHours) {
        alert(`❌ 希望時間が短すぎます\n\n最低 ${minHours} 時間以上の希望を入力してください。\n現在の入力: ${diffHours.toFixed(1)} 時間`);
        return false;
      }
      
      // ★★★ 営業時間内チェック（修正版） ★★★
      if (startMinutes < startLimitMinutes || startMinutes > endLimitMinutes) {
        alert(`開始時間は ${startLimit} 〜 ${endLimit} の範囲で入力してください。`);
        return false;
      }
      
      if (endMinutes < startLimitMinutes || endMinutes > endLimitMinutes) {
        alert(`終了時間は ${startLimit} 〜 ${endLimit} の範囲で入力してください。`);
        return false;
      }
      
      return true;
    }

    // 出勤有無の切り替え
    function toggleTimeInputs() {
      const workSelect = document.getElementById('workSelect');
      const startTime = document.getElementById('startTime');
      const endTime = document.getElementById('endTime');
      
      if (workSelect.value === '0') {
        startTime.disabled = true;
        endTime.disabled = true;
        startTime.required = false;
        endTime.required = false;
      } else {
        startTime.disabled = false;
        endTime.disabled = false;
        startTime.required = true;
        endTime.required = true;
      }
    }
    
    // ページ読み込み時に初期化
    document.addEventListener('DOMContentLoaded', toggleTimeInputs);

    

