document.addEventListener("DOMContentLoaded", function() {
    const calendarBody = document.getElementById("calendar-body");
    const monthYear = document.getElementById("monthYear");
    const prevMonthBtn = document.getElementById("prevMonth");
    const nextMonthBtn = document.getElementById("nextMonth");
    const modal = document.getElementById("shift-modal");
    const modalText = document.getElementById("modal-text");
    const closeBtn = document.getElementById("modal-close");

    // ✅ 締切日を基準に表示月を決定
    let currentDate = new Date();
    const today = new Date();
    const currentDay = today.getDate();
    
    // deadlineDay は HTMLから渡される（例: 15日）
    const deadlineDay = window.deadlineDay || 15;
    
    // 今日が締切日を過ぎていたら、翌々月を表示
    if (currentDay > deadlineDay) {
        currentDate.setMonth(currentDate.getMonth() + 2);
    } else {
        // 締切日前なら翌月を表示
        currentDate.setMonth(currentDate.getMonth() + 1);
    }
    
    const sentDates = window.sentDates || [];

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
            cell.dataset.date = dateStr;

            // ✅ チェックマーク表示
            if (sentDates.includes(dateStr)) {
                const check = document.createElement("span");
                check.textContent = "✅";
                check.style.marginLeft = "5px";
                cell.appendChild(check);
            }

            // ✅ クリックイベント
            cell.addEventListener("click", async () => {
                try {
                    const res = await fetch(`/makeshift/day/${dateStr}`);
                    if (!res.ok) throw new Error("データ取得に失敗しました");
                    const data = await res.json();
                    console.log("✅ 取得データ:", data);

                    // ====== モーダル内容を構築 ======
                    let message = `📅 ${data.date} の情報\n\n`;

                    // --- 登録ユーザー一覧 ---
                    if (!data.users || Object.keys(data.users).length === 0) {
                        message += "👥 登録なし\n\n";
                    } else {
                        for (const [user, times] of Object.entries(data.users)) {
                            message += `👤 ユーザーID: ${user}\n`;
                            for (const [s, e] of times) {
                                if (s === "出勤できない") {
                                    message += `  ❌ 出勤できない\n`;
                                } else {
                                    message += `  🕒 ${s}〜${e}\n`;
                                }
                            }
                            message += "\n";
                        }
                    }

                    // --- 空き時間一覧 ---
                    message += `🕓 空き時間:\n`;
                    if (data.free_slots && data.free_slots.length > 0) {
                        for (const [s, e] of data.free_slots) {
                            message += `  ✅ ${s}〜${e}\n`;
                        }
                    } else {
                        message += "  （空きなし）";
                    }

                    // ✅ モーダルに反映（改行保持）
                    // ✅ モーダルに反映（改行と絵文字保持）
                    modalText.innerHTML = message.replace(/\n/g, "<br>");
                    modal.style.display = "flex";

                } catch (err) {
                    console.error("❌ エラー:", err);
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

    // === モーダル閉じる処理 ===
    closeBtn.addEventListener("click", () => {
        modal.style.display = "none";
    });

    window.addEventListener("click", (e) => {
        if (e.target === modal) modal.style.display = "none";
    });

    // ✅ 初期表示
    renderCalendar();
});

const logoutLink = document.getElementById("logout-link");

if (logoutLink) { // 要素が存在することを確認
    logoutLink.addEventListener("click", function (e) {
        e.preventDefault();

        if (confirm("ログアウトしますか？")) {
            // data-logout-url属性の値を取得
            const logoutUrl = logoutLink.getAttribute("data-logout-url");

            if (logoutUrl) {
                window.location.href = logoutUrl;
            } else {
                // デバッグ用: URLが取得できなかった場合の警告
                console.error("ログアウトURLが設定されていません。");
            }
        }
    });
}
// ハンバーガーメニューの制御
const menuIcon = document.getElementById('menuIcon');
const menuCloseBtn = document.getElementById('closeBtn'); // 名前を変更
const sideMenu = document.getElementById('sideMenu');
const overlay = document.getElementById('overlay');

if (menuIcon && menuCloseBtn && sideMenu && overlay) {
    // メニューを開く
    menuIcon.addEventListener('click', function() {
        console.log('メニューアイコンクリック'); // デバッグ用
        sideMenu.classList.add('active');
        overlay.classList.add('active');
    });

    // メニューを閉じる
    menuCloseBtn.addEventListener('click', function() {
        console.log('閉じるボタンクリック'); // デバッグ用
        sideMenu.classList.remove('active');
        overlay.classList.remove('active');
    });

    // オーバーレイをクリックで閉じる
    overlay.addEventListener('click', function() {
        sideMenu.classList.remove('active');
        overlay.classList.remove('active');
    });
}