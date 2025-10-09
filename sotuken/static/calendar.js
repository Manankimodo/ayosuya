document.addEventListener("DOMContentLoaded", function() {
    const calendarBody = document.getElementById("calendar-body");
    const monthYear = document.getElementById("monthYear");
    const prevMonthBtn = document.getElementById("prevMonth");
    const nextMonthBtn = document.getElementById("nextMonth");
  
    let currentDate = new Date();
    window.alert('ログイン成功')
  
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
  
        // ✅ 日付クリックで sinsei.html に遷移
        cell.addEventListener("click", () => {
          window.location.href = `/sinsei/${dateStr}`;
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
  });
  