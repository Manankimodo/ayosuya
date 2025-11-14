document.addEventListener("DOMContentLoaded", function() {
  const calendarBody = document.getElementById("calendar-body");
  const monthYear = document.getElementById("monthYear");
  const prevMonthBtn = document.getElementById("prevMonth");
  const nextMonthBtn = document.getElementById("nextMonth");

  let currentDate = new Date();


  function renderCalendar() {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    monthYear.textContent = `${year}年 ${month + 1}月`;

    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);

    calendarBody.innerHTML = "";
    let row = document.createElement("tr");

    for (let i = 0; i < firstDay.getDay(); i++) {
      row.appendChild(document.createElement("td"));
    }

    for (let day = 1; day <= lastDay.getDate(); day++) {
      const cell = document.createElement("td");
      cell.textContent = day;

      const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;


        // ✅ チェックマーク表示（送信済みの日付なら）
      if (sentDates.includes(dateStr)) {
        const check = document.createElement("span");
        check.textContent = "✅";
        check.style.marginLeft = "5px";
        cell.appendChild(check);
      }

      // ✅ 日付クリックで sinsei.html に遷移
      cell.addEventListener("click", () => {
        window.location.href = `/calendar/sinsei/${dateStr}`;
      });

      row.appendChild(cell);

      if ((firstDay.getDay() + day) % 7 === 0) {
        calendarBody.appendChild(row);
        row = document.createElement("tr");
      }
    }

    calendarBody.appendChild(row);
  }

  prevMonthBtn.addEventListener("click", () => {
    currentDate.setMonth(currentDate.getMonth() - 1);
    renderCalendar();
  });

  nextMonthBtn.addEventListener("click", () => {
    currentDate.setMonth(currentDate.getMonth() + 1);
    renderCalendar();
  });

  // ✅ 通常起動時はカレンダー表示（ログイン後に checkAdminAfterLogin(true) を呼ぶ）
  renderCalendar();

  // --- Flask側テンプレートなどで埋め込み可能 ---
  // <script>
  //   checkAdminAfterLogin({{ login_success|tojson }});
  // </script>

 

  // 🍔 ハンバーガーメニュー開閉処理
  const hamburger = document.getElementById("hamburger");
  const menu = document.getElementById("menu");

  hamburger.addEventListener("click", () => {
    hamburger.classList.toggle("active");
    menu.classList.toggle("open");
  });

});


// データベースから提出済み日付を取得する処理はそのまま維持
const sentDates = JSON.parse(document.getElementById("sentDatesData").textContent);

// === 🍔 ハンバーガーメニュー動作 (初期化時に一度だけ登録) ===
const hamburger = document.getElementById('hamburger');
const menu = document.getElementById('menu');

if (hamburger && menu) {
    hamburger.addEventListener('click', () => {
        // メニューとアイコンの状態を切り替える
        hamburger.classList.toggle('active');
        menu.classList.toggle('active');
    });
}
// === 🔹 ログアウト確認アラート (初期化時に一度だけ登録) ===
const logoutLink = document.getElementById("logout-link");

if (logoutLink) {
    // ログアウトURLをdata属性から取得
    const logoutUrl = logoutLink.getAttribute('data-logout-url');
    
    logoutLink.addEventListener("click", function (e) {
        e.preventDefault(); 
        const confirmed = confirm("ログアウトしますか？");
        if (confirmed) {
            // 取得したURLを使用
            window.location.href = logoutUrl;
        }
    });
}
