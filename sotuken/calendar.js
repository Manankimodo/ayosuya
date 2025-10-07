
const calendarBody = document.getElementById("calendar-body");
const monthYear = document.getElementById("monthYear");

let today = new Date();
let currentMonth = today.getMonth();
let currentYear = today.getFullYear();

function renderCalendar(year, month) {
    calendarBody.innerHTML = "";
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const firstDayIndex = firstDay.getDay();
    const lastDate = lastDay.getDate();

    monthYear.textContent = `${year}年 ${month + 1}月`;

    let date = 1;
    for (let i = 0; i < 6; i++) {
    const row = document.createElement("tr");

    for (let j = 0; j < 7; j++) {
        const cell = document.createElement("td");
        if (i === 0 && j < firstDayIndex) {
        cell.classList.add("inactive");
        row.appendChild(cell);
        } else if (date > lastDate) {
        break;
        } else {
        cell.textContent = date;
        const yyyy = year;
        const mm = String(month + 1).padStart(2, "0");
        const dd = String(date).padStart(2, "0");
        const link = `/select/${yyyy}-${mm}-${dd}`;

        cell.addEventListener("click", () => {
            window.location.href = link;
        });

        row.appendChild(cell);
        date++;
        }
    }

    calendarBody.appendChild(row);
    }
}

document.getElementById("prevMonth").addEventListener("click", () => {
    currentMonth--;
    if (currentMonth < 0) {
    currentMonth = 11;
    currentYear--;
    }
    renderCalendar(currentYear, currentMonth);
});

document.getElementById("nextMonth").addEventListener("click", () => {
    currentMonth++;
    if (currentMonth > 11) {
    currentMonth = 0;
    currentYear++;
    }
    renderCalendar(currentYear, currentMonth);
});

renderCalendar(currentYear, currentMonth);
