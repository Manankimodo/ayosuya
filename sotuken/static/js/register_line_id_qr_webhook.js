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
  
  const role = window.LINE_CONFIG.userRole;
  const selRole = window.LINE_CONFIG.selectedRole;
  const effectiveRole = selRole || role;

  // 1. まずコンソールで何が起きているか見る
  console.log("Debug Info:", { role, selRole, effectiveRole });

  if (effectiveRole === 'manager') {
    window.location.href = window.LINE_CONFIG.managerHomeUrl;
    return;
  } 
  
  // 2. staff、またはそれ以外の従業員の場合
  if (window.LINE_CONFIG.calendarUrl) {
    window.location.href = window.LINE_CONFIG.calendarUrl;
  } else {
    // URL自体が渡ってきていない場合のフォールバック
    window.location.href = '/'; 
  }
}

function skipRegistration() {
  if (pollInterval) clearInterval(pollInterval);
  goHome();
}