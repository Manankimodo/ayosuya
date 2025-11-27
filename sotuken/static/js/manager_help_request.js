document.addEventListener("DOMContentLoaded", function() {
  const calendarBody = document.getElementById("calendar-body");
  const monthYear = document.getElementById("monthYear");
  const prevMonthBtn = document.getElementById("prevMonth");
  const nextMonthBtn = document.getElementById("nextMonth");

  let currentDate = new Date();

  function renderCalendar() {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    monthYear.textContent = `${year}年 ${month + 1}月 - 店長のヘルプ希望申請`;

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

      const dayNumber = document.createElement("span");
      dayNumber.classList.add("day-number");
      dayNumber.textContent = day;
      cell.appendChild(dayNumber);

      const shiftContent = document.createElement("div");
      shiftContent.classList.add("shift-content");

      if (sentDates.includes(dateStr)) {
        const check = document.createElement("span");
        check.classList.add("event-indicator");
        check.textContent = "✔";
        
        shiftContent.appendChild(check);
        cell.classList.add('has-shift');
      }

      const timeInputContainer = document.createElement("div");
      timeInputContainer.classList.add("time-input-container");
      shiftContent.appendChild(timeInputContainer);

      cell.appendChild(shiftContent);

      // ✅ 日付クリックでヘルプ希望申請フォームに遷移
      cell.addEventListener("click", () => {
        window.location.href = `/calendar/manager_help_sinsei/${dateStr}`;
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

  renderCalendar();

  // 🍔 ハンバーガーメニュー開閉処理
  const hamburger = document.getElementById("hamburger");
  const menu = document.getElementById("menu");

  hamburger.addEventListener("click", () => {
    hamburger.classList.toggle("active");
    menu.classList.toggle("open");
  });
});

const sentDates = JSON.parse(document.getElementById("sentDatesData").textContent);

const hamburger = document.getElementById('hamburger');
const menu = document.getElementById('menu');

if (hamburger && menu) {
    hamburger.addEventListener('click', () => {
        hamburger.classList.toggle('active');
        menu.classList.toggle('active');
    });
}

const logoutLink = document.getElementById("logout-link");

if (logoutLink) {
    const logoutUrl = logoutLink.getAttribute('data-logout-url');
    
    logoutLink.addEventListener("click", function (e) {
        e.preventDefault(); 
        const confirmed = confirm("ログアウトしますか？");
        if (confirmed) {
            if (logoutUrl) {
                window.location.href = logoutUrl;
            }
        }
    });
}