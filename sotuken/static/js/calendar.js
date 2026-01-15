// MovieShift カレンダー JavaScript (月記憶機能付き)

document.addEventListener("DOMContentLoaded", function() {
  const calendarBody = document.getElementById("calendar-body");
  const monthYear = document.getElementById("monthYear");
  const prevMonthBtn = document.getElementById("prevMonth");
  const nextMonthBtn = document.getElementById("nextMonth");

  let currentDate = new Date();

  // ★ URLパラメータから月を取得する関数
  function getMonthFromURL() {
    const urlParams = new URLSearchParams(window.location.search);
    const monthParam = urlParams.get('month');
    
    if (monthParam) {
      // month=2026-02 の形式
      const [year, month] = monthParam.split('-').map(Number);
      if (year && month >= 1 && month <= 12) {
        return new Date(year, month - 1, 1);
      }
    }
    return null;
  }

  // ★ ローカルストレージから最後に見た月を取得
  function getLastViewedMonth() {
    const stored = localStorage.getItem('calendar_last_month');
    if (stored) {
      const [year, month] = stored.split('-').map(Number);
      if (year && month >= 1 && month <= 12) {
        return new Date(year, month - 1, 1);
      }
    }
    return null;
  }

  // ★ 現在の月をローカルストレージに保存
  function saveCurrentMonth() {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth() + 1;
    localStorage.setItem('calendar_last_month', `${year}-${String(month).padStart(2, '0')}`);
  }

  // ★ URLを更新（履歴に追加せずに）
  function updateURL() {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth() + 1;
    const newURL = `${window.location.pathname}?month=${year}-${String(month).padStart(2, '0')}`;
    window.history.replaceState({}, '', newURL);
  }

  // ★ 初期月の決定（優先順位: URL > ローカルストレージ > 今月）
  const urlMonth = getMonthFromURL();
  const storedMonth = getLastViewedMonth();
  
  if (urlMonth) {
    currentDate = urlMonth;
  } else if (storedMonth) {
    currentDate = storedMonth;
  }

  // カレンダーレンダリング関数
  function renderCalendar() {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    monthYear.textContent = `${year}年 ${month + 1}月`;

    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);

    calendarBody.innerHTML = "";
    let row = document.createElement("tr");

    // 月初めの空白セル
    for (let i = 0; i < firstDay.getDay(); i++) {
      row.appendChild(document.createElement("td"));
    }

    // 日付セルの生成
    for (let day = 1; day <= lastDay.getDate(); day++) {
      const cell = document.createElement("td");
      
      const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;

      // 1. 日付番号コンテナ (.day-number) を作成
      const dayNumber = document.createElement("span");
      dayNumber.classList.add("day-number");
      dayNumber.textContent = day;
      cell.appendChild(dayNumber);

      // 2. シフト内容コンテナ (.shift-content) を作成
      const shiftContent = document.createElement("div");
      shiftContent.classList.add("shift-content");

      // ✅ チェックマーク表示（送信済みの日付なら）
      if (sentDates.includes(dateStr)) {
        const check = document.createElement("span");
        check.classList.add("event-indicator");
        check.textContent = "✔";
        
        shiftContent.appendChild(check);
        cell.classList.add('has-shift');
      }

      // 3. 時間入力フィールドコンテナを作成
      const timeInputContainer = document.createElement("div");
      timeInputContainer.classList.add("time-input-container");
      
      shiftContent.appendChild(timeInputContainer);
      cell.appendChild(shiftContent);

      // ✅ 日付クリックで sinsei.html に遷移（現在の月をURLパラメータで渡す）
      cell.addEventListener("click", () => {
        const currentMonth = `${year}-${String(month + 1).padStart(2, '0')}`;
        window.location.href = `/calendar/sinsei/${dateStr}?return_month=${currentMonth}`;
      });

      row.appendChild(cell);

      // 週の終わりで改行
      if ((firstDay.getDay() + day) % 7 === 0) {
        calendarBody.appendChild(row);
        row = document.createElement("tr");
      }
    }

    calendarBody.appendChild(row);
    
    // ★ 月の表示後、その月を記憶
    saveCurrentMonth();
    updateURL();
  }

  // 月切り替えイベント
  prevMonthBtn.addEventListener("click", () => {
    currentDate.setMonth(currentDate.getMonth() - 1);
    renderCalendar();
  });

  nextMonthBtn.addEventListener("click", () => {
    currentDate.setMonth(currentDate.getMonth() + 1);
    renderCalendar();
  });

  // 初回カレンダー表示
  renderCalendar();

  // === 📱 ボトムナビゲーション アクティブ状態管理 ===
  const navItems = document.querySelectorAll('.nav-item');
  const currentPath = window.location.pathname;

  if (navItems.length > 0) {
    // 現在のページに対応するナビアイテムをアクティブ化
    navItems.forEach(item => {
      const href = item.getAttribute('href');
      
      // パスが完全一致、または部分一致（サブページ対応）
      if (href === currentPath || currentPath.startsWith(href)) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    // ナビアイテムクリック時のフィードバック
    navItems.forEach(item => {
      item.addEventListener('click', function(e) {
        // タップ時の視覚フィードバック（スケールアニメーション）
        this.style.transform = 'scale(0.95)';
        setTimeout(() => {
          this.style.transform = '';
        }, 150);
      });
    });
  }

  // === 🚪 ログアウト処理 ===
  const logoutLink = document.getElementById("logout-link");

  if (logoutLink) {
    const logoutUrl = logoutLink.getAttribute('data-logout-url');
    
    logoutLink.addEventListener("click", function (e) {
      e.preventDefault(); 
      const confirmed = confirm("ログアウトしますか？");
      if (confirmed && logoutUrl) {
        window.location.href = logoutUrl;
      }
    });
  }

});

// === 📊 データベースから提出済み日付を取得 ===
const sentDatesElement = document.getElementById("sentDatesData");
const sentDates = sentDatesElement ? JSON.parse(sentDatesElement.textContent) : [];

// === 🎯 ページ固有のアクティブ状態設定（オプション） ===
// 特定のページでナビゲーションアイテムを強制的にアクティブ化したい場合
function setActiveNavItem(pageName) {
  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(item => {
    const label = item.querySelector('.nav-label');
    if (label && label.textContent === pageName) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });
}

// 使用例: setActiveNavItem('カレンダー'); を他のページで呼び出せます