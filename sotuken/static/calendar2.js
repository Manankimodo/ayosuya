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

        // 空白セルを最初に追加
        for (let i = 0; i < firstDay.getDay(); i++) {
            row.appendChild(document.createElement("td"));
        }

        // 日付セル生成
        for (let day = 1; day <= lastDay.getDate(); day++) {
            const cell = document.createElement("td");
            cell.textContent = day;

            const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
            cell.dataset.date = dateStr; // ✅ クリック時に使う

            // ✅ チェックマーク表示（送信済みの日付なら）
            if (sentDates.includes(dateStr)) {
                const check = document.createElement("span");
                check.textContent = "✅";
                check.style.marginLeft = "5px";
                cell.appendChild(check);
            }

            // ✅ 管理者：日付クリックで全ユーザーの登録状況を取得
            cell.addEventListener("click", async () => {
                try {
                    const res = await fetch(`/makeshift/day/${dateStr}`);
                    if (!res.ok) throw new Error("データ取得に失敗しました");
                    const data = await res.json();

                    let message = `📅 ${data.date} の情報\n\n`;

                    if (Object.keys(data.users).length === 0) {
                        message += "登録なし";
                    } else {
                        for (const [user, times] of Object.entries(data.users)) {
                            message += `👤 ${user}\n`;
                            for (const [s, e] of times) {
                                message += `  登録: ${s}〜${e}\n`;
                            }
                            message += "\n";
                        }

                        message += `🕒 空き時間:\n`;
                        for (const [s, e] of data.free_slots) {
                            message += `  ${s}〜${e}\n`;
                        }
                    }

                    alert(message);
                } catch (err) {
                    alert("エラーが発生しました：" + err.message);
                }
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

    // ✅ 初期表示
    renderCalendar();
});
