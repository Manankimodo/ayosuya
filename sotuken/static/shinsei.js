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