// ★ 15分刻みの時間オプションを生成する関数
function generateTimeOptions(startLimit, endLimit) {
  const options = [];
  const [startHour, startMin] = startLimit.split(':').map(Number);
  const [endHour, endMin] = endLimit.split(':').map(Number);
  
  let currentHour = startHour;
  let currentMin = startMin;
  
  // 開始時刻の分を15分刻みに調整
  currentMin = Math.ceil(currentMin / 15) * 15;
  if (currentMin === 60) {
    currentMin = 0;
    currentHour += 1;
  }
  
  const endTotalMin = endHour * 60 + endMin;
  
  while (true) {
    const currentTotalMin = currentHour * 60 + currentMin;
    if (currentTotalMin > endTotalMin) break;
    
    const timeStr = `${String(currentHour).padStart(2, '0')}:${String(currentMin).padStart(2, '0')}`;
    options.push(timeStr);
    
    // 次の15分を計算
    currentMin += 15;
    if (currentMin >= 60) {
      currentMin = 0;
      currentHour += 1;
    }
    
    if (currentHour >= 24) break;
  }
  
  return options;
}

// ★ time inputをselectに置き換える関数
function replaceTimeInputsWithSelect() {
  const startTime = document.getElementById('startTime');
  const endTime = document.getElementById('endTime');
  const settings = document.getElementById('shift-settings');
  
  if (!startTime || !endTime || !settings) return;
  
  const startLimit = settings.dataset.startLimit;
  const endLimit = settings.dataset.endLimit;
  const timeOptions = generateTimeOptions(startLimit, endLimit);
  
  // 現在の値を保存
  const currentStartValue = startTime.value;
  const currentEndValue = endTime.value;
  const isDisabled = startTime.disabled;
  
  // 開始時間のselectを作成
  const startSelect = document.createElement('select');
  startSelect.id = 'startTime';
  startSelect.name = 'start_time';
  startSelect.required = !isDisabled;
  startSelect.disabled = isDisabled;
  startSelect.style.cssText = startTime.style.cssText;
  
  // 空のオプションを追加
  const startEmptyOption = document.createElement('option');
  startEmptyOption.value = '';
  startEmptyOption.textContent = '-- 選択してください --';
  startSelect.appendChild(startEmptyOption);
  
  // 時間オプションを追加
  timeOptions.forEach(time => {
    const option = document.createElement('option');
    option.value = time;
    option.textContent = time;
    if (time === currentStartValue) {
      option.selected = true;
    }
    startSelect.appendChild(option);
  });
  
  // 終了時間のselectを作成
  const endSelect = document.createElement('select');
  endSelect.id = 'endTime';
  endSelect.name = 'end_time';
  endSelect.required = !isDisabled;
  endSelect.disabled = isDisabled;
  endSelect.style.cssText = endTime.style.cssText;
  
  // 空のオプションを追加
  const endEmptyOption = document.createElement('option');
  endEmptyOption.value = '';
  endEmptyOption.textContent = '-- 選択してください --';
  endSelect.appendChild(endEmptyOption);
  
  // 時間オプションを追加
  timeOptions.forEach(time => {
    const option = document.createElement('option');
    option.value = time;
    option.textContent = time;
    if (time === currentEndValue) {
      option.selected = true;
    }
    endSelect.appendChild(option);
  });
  
  // 元のinputを置き換え
  startTime.parentNode.replaceChild(startSelect, startTime);
  endTime.parentNode.replaceChild(endSelect, endTime);
}

// 出勤有無の切り替え
function toggleTimeInputs() {
  const workSelect = document.getElementById('workSelect');
  const startTime = document.getElementById('startTime');
  const endTime = document.getElementById('endTime');
  
  if (!workSelect || !startTime || !endTime) return;
  
  if (workSelect.value === '0') {
    // 出勤不可なら時間入力を無効化＆値をクリア
    startTime.disabled = true;
    endTime.disabled = true;
    startTime.required = false;
    endTime.required = false;
    startTime.value = '';
    endTime.value = '';
  } else {
    // 出勤可能なら時間入力を有効化
    startTime.disabled = false;
    endTime.disabled = false;
    startTime.required = true;
    endTime.required = true;
  }
}

// バリデーション関数
function validateForm() {
  const workSelect = document.getElementById('workSelect');
  
  // 出勤不可の場合はチェック不要
  if (workSelect.value === '0') {
    return true;
  }
  
  const startTime = document.getElementById('startTime').value;
  const endTime = document.getElementById('endTime').value;
  
  if (!startTime || !endTime) {
    alert('開始時間と終了時間を選択してください。');
    return false;
  }
  
  const settings = document.getElementById('shift-settings');
  const minHours = parseFloat(settings.dataset.minHours);
  const startLimit = settings.dataset.startLimit;
  const endLimit = settings.dataset.endLimit;
  
  // 時刻を分単位に変換
  function timeToMinutes(timeStr) {
    const [hours, minutes] = timeStr.split(':').map(Number);
    return hours * 60 + minutes;
  }
  
  const startMinutes = timeToMinutes(startTime);
  const endMinutes = timeToMinutes(endTime);
  const startLimitMinutes = timeToMinutes(startLimit);
  const endLimitMinutes = timeToMinutes(endLimit);
  
  // ★ 終了時間が開始時間以下の場合（同じ時刻または逆転）をチェック
  if (endMinutes <= startMinutes) {
    alert(`❌ 時間設定エラー\n\n終了時間は開始時間より後に設定してください。\n\n現在の設定:\n開始: ${startTime}\n終了: ${endTime}`);
    return false;
  }
  
  // 時間差を計算
  const start = new Date(`2000-01-01T${startTime}:00`);
  const end = new Date(`2000-01-01T${endTime}:00`);
  
  let diffHours = (end - start) / (1000 * 60 * 60);
  
  // 日付をまたぐ場合の処理（この時点では発生しないが念のため）
  if (diffHours <= 0) {
    diffHours += 24;
  }
  
  // 最低勤務時間チェック
  if (diffHours < minHours) {
    alert(`❌ 希望時間が短すぎます\n\n最低 ${minHours} 時間以上の希望を入力してください。\n現在の入力: ${diffHours.toFixed(1)} 時間`);
    return false;
  }
  
  // 営業時間内チェック
  if (startMinutes < startLimitMinutes || startMinutes > endLimitMinutes) {
    alert(`開始時間は ${startLimit} 〜 ${endLimit} の範囲で選択してください。`);
    return false;
  }
  
  if (endMinutes < startLimitMinutes || endMinutes > endLimitMinutes) {
    alert(`終了時間は ${startLimit} 〜 ${endLimit} の範囲で選択してください。`);
    return false;
  }
  
  return true;
}

// 保存アクション設定
function setSaveAction(action) {
  const saveActionInput = document.getElementById('saveAction');
  if (saveActionInput) {
    saveActionInput.value = action;
  }
  return true;
}

// ページ読み込み時の初期化
document.addEventListener('DOMContentLoaded', function() {
  // time inputをselectに置き換え
  replaceTimeInputsWithSelect();
  
  // 初期状態を反映
  toggleTimeInputs();
  
  // 出勤有無の変更イベント
  const workSelect = document.getElementById('workSelect');
  if (workSelect) {
    workSelect.addEventListener('change', toggleTimeInputs);
  }
});