document.addEventListener("DOMContentLoaded", function() {
    const calendarBody = document.getElementById("calendar-body");
    const monthYear = document.getElementById("monthYear");
    const prevMonthBtn = document.getElementById("prevMonth");
    const nextMonthBtn = document.getElementById("nextMonth");

    // --- モーダル要素を取得 ---
    const modal = document.getElementById("modal");
    const modalTitle = document.getElementById("modalTitle");
    const modalBody = document.getElementById("modalBody");
    const closeModal = document.getElementById("closeModal");

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
            cell.dataset.date = dateStr;

            // ✅ チェックマーク表示
            if (sentDates.includes(dateStr)) {
                const check = document.createElement("span");
                check.textContent = "✅";
                check.style.marginLeft = "5px";
                cell.appendChild(check);
            }

            // ✅ 管理者クリック処理（モーダル表示）
            cell.addEventListener("click", async () => {
                try {
                    const res = await fetch(`/makeshift/day/${dateStr}`);
                    if (!res.ok) throw new Error("データ取得に失敗しました");
                    const data = await res.json();

                    modalTitle.textContent = `📅 ${data.date} の登録情報`;

                    if (Object.keys(data.users).length === 0) {
                        modalBody.textContent = "登録されたデータがありません。";
                    } else {
                        let message = "";

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

                        modalBody.textContent = message;
                    }

                    // モーダルを表示
                    modal.style.display = "block";

                } catch (err) {
                    modalTitle.textContent = "エラー";
                    modalBody.textContent = err.message;
                    modal.style.display = "block";
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

    // --- モーダル閉じる処理 ---
    closeModal.addEventListener("click", () => {
        modal.style.display = "none";
    });
    window.addEventListener("click", (e) => {
        if (e.target === modal) {
            modal.style.display = "none";
        }
    });

    // ✅ 初期表示
    renderCalendar();
});
