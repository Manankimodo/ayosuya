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
        check.classList.add("event-indicator"); // CSSのスタイルを適用
        check.textContent = "✔"; // "✅"から"✔"に変更。CSSでは"✔"を想定
        
        shiftContent.appendChild(check);
        cell.classList.add('has-shift'); // 提出済みセルの背景を強調
      }


      // 3. 時間入力フィールド (.time-input-container) を作成 (常に追加)
      //    ※ 提出済みかどうかに関わらず、クリックでモーダル等が開くことを想定し、
      //       ここではCSS構造のみ作成します。
      const timeInputContainer = document.createElement("div");
      timeInputContainer.classList.add("time-input-container");
      
      // 仮の入力フィールド (実際の入力はsinsei.htmlで行う前提)
      // ここで input 要素を生成して追加すれば、カレンダー画面で入力可能になります。
      // 例: const input = document.createElement("input");
      //     input.type = "text";
      //     timeInputContainer.appendChild(input); 

      // シフト内容コンテナにチェックと入力コンテナを追加
      shiftContent.appendChild(timeInputContainer);

      // 最終的にセルに shift-content を追加
      cell.appendChild(shiftContent);


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
  
  // (以降のイベントリスナー、ハンバーガーメニュー、ログアウト処理はそのまま)
  // ...

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
const logoutLink = document.getElementById("logout-link");

if (logoutLink) {
    // ログアウトURLをdata属性から取得 (HTML側に data-logout-url="{{ url_for('login.logout') }}" が必要)
    const logoutUrl = logoutLink.getAttribute('data-logout-url');
    
    logoutLink.addEventListener("click", function (e) {
        e.preventDefault(); 
        const confirmed = confirm("ログアウトしますか？");
        if (confirmed) {
            // 取得したURLを使用
            if (logoutUrl) {
                window.location.href = logoutUrl;
            }
        }
    });
}
