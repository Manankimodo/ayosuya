document.addEventListener("DOMContentLoaded", function() {
  const calendarBody = document.getElementById("calendar-body");
  const monthYear = document.getElementById("monthYear");
  const prevMonthBtn = document.getElementById("prevMonth");
  const nextMonthBtn = document.getElementById("nextMonth");

  // 要素の存在確認
  if (!calendarBody || !monthYear || !prevMonthBtn || !nextMonthBtn) {
    console.error('必要な要素が見つかりません:', {
      calendarBody: !!calendarBody,
      monthYear: !!monthYear,
      prevMonthBtn: !!prevMonthBtn,
      nextMonthBtn: !!nextMonthBtn
    });
    return;
  }

  let currentDate = new Date();

  function renderCalendar() {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    monthYear.textContent = `${year}年 ${month + 1}月 - 店長のヘルプ希望申請`;

    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);

    calendarBody.innerHTML = "";
    let row = document.createElement("tr");

    // 月初の空白セル
    for (let i = 0; i < firstDay.getDay(); i++) {
      row.appendChild(document.createElement("td"));
    }

    // 日付セル
    for (let day = 1; day <= lastDay.getDate(); day++) {
      const cell = document.createElement("td");
      
      const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;

      // 日付番号
      const dayNumber = document.createElement("span");
      dayNumber.classList.add("day-number");
      dayNumber.textContent = day;
      cell.appendChild(dayNumber);

      // シフト内容コンテナ
      const shiftContent = document.createElement("div");
      shiftContent.classList.add("shift-content");

      // 申請済み日付にチェックマーク
      if (typeof sentDates !== 'undefined' && sentDates.includes(dateStr)) {
        const check = document.createElement("span");
        check.classList.add("event-indicator");
        check.textContent = "✔";
        
        shiftContent.appendChild(check);
        cell.classList.add('has-shift');
      }

      // 時間入力コンテナ
      const timeInputContainer = document.createElement("div");
      timeInputContainer.classList.add("time-input-container");
      shiftContent.appendChild(timeInputContainer);

      cell.appendChild(shiftContent);

      // 日付クリックで申請ページへ遷移
      cell.addEventListener("click", () => {
        window.location.href = `/calendar/manager_help_sinsei/${dateStr}`;
      });

      row.appendChild(cell);

      // 週の最終日で改行
      if ((firstDay.getDay() + day) % 7 === 0) {
        calendarBody.appendChild(row);
        row = document.createElement("tr");
      }
    }

    // 最後の行を追加
    if (row.children.length > 0) {
      calendarBody.appendChild(row);
    }
  }

  // 前月・次月ボタン
  prevMonthBtn.addEventListener("click", () => {
    currentDate.setMonth(currentDate.getMonth() - 1);
    renderCalendar();
  });

  nextMonthBtn.addEventListener("click", () => {
    currentDate.setMonth(currentDate.getMonth() + 1);
    renderCalendar();
  });

  // 初回レンダリング
  renderCalendar();

  // 🍔 ハンバーガーメニューの制御（HTMLの要素に合わせて修正）
  const menuIcon = document.getElementById('menuIcon');
  const menuCloseBtn = document.getElementById('closeBtn');
  const sideMenu = document.getElementById('sideMenu');
  const overlay = document.getElementById('overlay');

  if (menuIcon && menuCloseBtn && sideMenu && overlay) {
    // メニューを開く
    menuIcon.addEventListener('click', function() {
      console.log('メニューアイコンクリック');
      sideMenu.classList.add('active');
      overlay.classList.add('active');
    });

    // メニューを閉じる
    menuCloseBtn.addEventListener('click', function() {
      console.log('閉じるボタンクリック');
      sideMenu.classList.remove('active');
      overlay.classList.remove('active');
    });

    // オーバーレイクリックで閉じる
    overlay.addEventListener('click', function() {
      sideMenu.classList.remove('active');
      overlay.classList.remove('active');
    });
  }
});

// sentDatesの取得（エラーハンドリング付き）
let sentDates = [];
try {
  const sentDatesElement = document.getElementById("sentDatesData");
  if (sentDatesElement && sentDatesElement.textContent) {
    sentDates = JSON.parse(sentDatesElement.textContent);
  }
} catch (error) {
  console.error('sentDatesの読み込みエラー:', error);
}

// ログアウト機能（現在のHTMLには存在しないが、念のため残す）
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