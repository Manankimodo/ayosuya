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
  
  // window.LINE_CONFIGから値を取得
  const effectiveRole = window.LINE_CONFIG.selectedRole || window.LINE_CONFIG.userRole;
  
  if (effectiveRole === 'manager') {
    // 管理者画面へ
    window.location.href = window.LINE_CONFIG.managerHomeUrl;
  } else {
    // 従業員画面へ
    window.location.href = window.LINE_CONFIG.calendarUrl;
  }
}

function skipRegistration() {
  if (pollInterval) clearInterval(pollInterval);
  goHome();
}