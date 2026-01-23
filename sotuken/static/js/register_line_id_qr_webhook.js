// LINE ID登録機能
let registrationInProgress = false;
let pollInterval = null;

async function startRegistration() {
  if (registrationInProgress) return;

  const startBtn = document.getElementById('start-btn');
  const loadingDiv = document.getElementById('loading');

  registrationInProgress = true;
  startBtn.disabled = true;
  loadingDiv.style.display = 'block';

  try {
    const response = await fetch(window.LINE_CONFIG.startRegistrationUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      }
    });

    const data = await response.json();

    if (response.ok) {
      showMessage('✅ 登録を開始しました。公式LINEにメッセージを送ってください。', 'info');
      startPolling();
    } else {
      showMessage(data.message || 'エラーが発生しました', 'error');
      startBtn.disabled = false;
      registrationInProgress = false;
    }
  } catch (error) {
    console.error('Error:', error);
    showMessage('通信エラーが発生しました', 'error');
    startBtn.disabled = false;
    registrationInProgress = false;
  } finally {
    loadingDiv.style.display = 'none';
  }
}

function startPolling() {
  const maxAttempts = 20;
  let attempts = 0;

  pollInterval = setInterval(() => {
    attempts++;

    if (attempts > maxAttempts) {
      clearInterval(pollInterval);
      showMessage('⏱️ 登録期限が切れました。もう一度開始ボタンをクリックしてください。', 'error');
      registrationInProgress = false;
      document.getElementById('start-btn').disabled = false;
      return;
    }

    checkRegistrationStatus();
  }, 30000);
}

async function checkRegistrationStatus() {
  try {
    const response = await fetch(window.LINE_CONFIG.checkRegistrationUrl, {
      method: 'GET'
    });

    const data = await response.json();

    if (data.registered) {
      clearInterval(pollInterval);
      updateStatusBox(true);
      showMessage('✅ LINE ID の登録が完了しました！', 'success');
      
      setTimeout(() => {
        goHome();
      }, 2000);
    }
  } catch (error) {
    console.error('Error checking status:', error);
  }
}

function updateStatusBox(registered) {
  const icon = document.getElementById('status-icon');
  const text = document.getElementById('status-text');
  const hint = document.getElementById('status-hint');

  if (registered) {
    icon.textContent = '✅';
    text.textContent = '登録完了！';
    text.classList.remove('waiting');
    text.classList.add('registered');
    hint.textContent = 'ホーム画面に遷移します...';
  }
}

function showMessage(message, type) {
  const messageAlert = document.getElementById('message-alert');
  messageAlert.textContent = message;
  messageAlert.className = `alert alert-${type}`;
  messageAlert.style.display = 'block';
}

function goHome() {
  if (pollInterval) clearInterval(pollInterval);
  
  const role = window.LINE_CONFIG.userRole || '';
  const selRole = window.LINE_CONFIG.selectedRole || '';
  
  // ★ selected_roleが設定されている場合は、それを優先（管理者が従業員として入っている場合）
  // selected_roleが空の場合は、通常のroleを使用
  const effectiveRole = selRole || role;

  // デバッグ用ログ
  console.log("🔍 LINE ID登録後の遷移先判定:", { 
    userRole: role,
    selectedRole: selRole,
    effectiveRole: effectiveRole,
    判定結果: selRole ? '「従業員として入る」モード' : '通常ログイン'
  });

  // 管理者判定（'manager'、'admin'、'administrator' などに対応）
  const isManager = ['manager', 'admin', 'administrator'].includes(effectiveRole.toLowerCase());
  
  if (isManager) {
    console.log("✅ 管理者として管理画面に遷移:", window.LINE_CONFIG.managerHomeUrl);
    window.location.href = window.LINE_CONFIG.managerHomeUrl;
    return;
  }
  
  // 従業員の場合
  if (window.LINE_CONFIG.calendarUrl) {
    console.log("✅ 従業員としてカレンダーに遷移:", window.LINE_CONFIG.calendarUrl);
    window.location.href = window.LINE_CONFIG.calendarUrl;
  } else {
    console.warn("⚠️ カレンダーURLが設定されていません。ルートにリダイレクトします。");
    window.location.href = '/calendar';
  }
}

function skipRegistration() {
  const config = window.LINE_CONFIG;
  const role = config.userRole || '';
  const selRole = config.selectedRole || '';
  
  // 登録成功時(goHome)と同じロジックで判定用ロールを決定
  const effectiveRole = selRole || role;

  // 管理者判定（大文字小文字を区別せず、manager/admin系をチェック）
  const isManager = ['manager', 'admin', 'administrator'].includes(effectiveRole.toLowerCase());

  if (isManager) {
    console.log("✅ 管理者としてキャンセル遷移:", config.managerHomeUrl);
    window.location.href = config.managerHomeUrl;
  } else {
    // 従業員の場合
    if (config.calendarUrl) {
      console.log("✅ 従業員としてキャンセル遷移:", config.calendarUrl);
      window.location.href = config.calendarUrl;
    } else {
      console.warn("⚠️ カレンダーURL不明のためルートへ");
      window.location.href = '/calendar';
    }
  }
}