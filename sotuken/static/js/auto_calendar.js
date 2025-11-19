// ==========================================
// 4. ▼▼▼ ハンバーガーメニュー制御ロジック ▼▼▼
// ==========================================
document.addEventListener("DOMContentLoaded", function() {
    // ... (既存のチャート描画ロジックがここにある) ...

    // ▼ 新規追加
    const menuBtn = document.getElementById('menuBtn');
    const sideMenu = document.getElementById('sideMenu');

    if (menuBtn && sideMenu) {
        // メニューボタンがクリックされたら
        menuBtn.addEventListener('click', function() {
            // ボタン自体にactiveクラスをトグル (X字に変化させるため)
            menuBtn.classList.toggle('active');
            // サイドメニューにactiveクラスをトグル (画面内に表示させるため)
            sideMenu.classList.toggle('active');
        });
        
        // メニューリンクをクリックしたらメニューを閉じる (UX向上のため)
        const menuLinks = sideMenu.querySelectorAll('a');
        menuLinks.forEach(link => {
            link.addEventListener('click', function() {
                menuBtn.classList.remove('active');
                sideMenu.classList.remove('active');
            });
        });
    }

});
// ==========================================
// 🎨 Chart.js ダークモード用設定 (全体適用)
// ==========================================

// デフォルトの文字色を「白」にする
Chart.defaults.color = '#000000ff';
Chart.defaults.borderColor = '#333333'; // グリッド線の色を薄いグレーに

// タイトル等のフォントも少し大きく調整（任意）
Chart.defaults.font.family = '"Helvetica Neue", "Arial", sans-serif';
const logoutLink = document.getElementById("logout-link");
// ==========================================
// ヘルプ募集機能 (独立して定義)
// ==========================================
function openHelpModal() {
    const modal = document.getElementById('helpModal');
    if(modal) {
        modal.style.display = 'flex';
        
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('helpDate').value = today;

        const now = new Date();
        now.setHours(now.getHours() + 1);
        const h = String(now.getHours()).padStart(2, '0');
        document.getElementById('helpStart').value = `${h}:00`;
    }
}

function closeHelpModal() {
    const modal = document.getElementById('helpModal');
    if(modal) modal.style.display = 'none';
}

async function submitHelpRequest() {
    const date = document.getElementById('helpDate').value;
    const start = document.getElementById('helpStart').value;
    const end = document.getElementById('helpEnd').value;

    if(!date || !start || !end) {
        alert("日時をすべて入力してください");
        return;
    }

    if(!confirm(`【確認】\n${date} ${start}〜${end}\n\n通知を送信しますか？`)) return;

    const submitBtn = document.querySelector('#helpModal .btn.danger');
    const originalText = submitBtn.innerText;

    try {
        submitBtn.disabled = true;
        submitBtn.innerText = "送信中...";

        const response = await fetch('/makeshift/api/help/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date, start_time: start, end_time: end })
        });

        const result = await response.json();
        if(response.ok) {
            alert(`✅ 配信完了！対象: ${result.target_count}名`);
            closeHelpModal();
        } else {
            alert("エラー: " + result.error);
        }
    } catch(e) {
        console.error(e);
        alert("通信エラーが発生しました");
    } finally {
        if(submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerText = originalText;
        }
    }
}

// モーダル外クリックで閉じる
window.onclick = function(event) {
    const modal = document.getElementById('helpModal');
    if (event.target == modal) closeHelpModal();
}

// ==========================================
// グラフ描画ロジック (読み込み完了後に実行)
// ==========================================
document.addEventListener("DOMContentLoaded", function() {
    // ★ここが変更点：HTMLで定義した変数からデータを取得
    const shiftData = window.flaskData.shifts;
    const settings = window.flaskData.settings;
    const chartsDiv = document.getElementById("charts");
    
    // データチェック
    if (!shiftData || shiftData.length === 0 || !chartsDiv) return;

    // 設定から時間を取得
    const minTime = settings.start_time ? new Date(`1970-01-01T${settings.start_time}:00`) : new Date("1970-01-01T08:00:00");
    const maxTime = settings.end_time ? new Date(`1970-01-01T${settings.end_time}:00`) : new Date("1970-01-01T22:00:00");

    const validData = shiftData.filter(s => s.start_time && s.end_time);
    const groupedByDateAndUser = {};

    validData.forEach(s => {
        const date = s.date;
        const userId = s.user_id;
        if (!groupedByDateAndUser[date]) groupedByDateAndUser[date] = {};
        if (!groupedByDateAndUser[date][userId]) groupedByDateAndUser[date][userId] = [];
        groupedByDateAndUser[date][userId].push(s);
    });

    const baseColors = ["hsl(0, 70%, 60%)", "hsl(70, 70%, 60%)", "hsl(140, 70%, 60%)", "hsl(210, 70%, 60%)", "hsl(280, 70%, 60%)"];
    const colors = {};
    let colorIndex = 0;

    // 日付ごとにループしてグラフ生成
    Object.entries(groupedByDateAndUser).forEach(([date, userShifts], idx) => {
        const container = document.createElement("div");
        container.classList.add("chart-container");
        // スタイルをJSで当てる場合（CSSファイルに書く方がより良いです）
        container.style.marginBottom = "30px";
        container.style.padding = "10px";
        container.style.background = "#fff";
        container.style.borderRadius = "8px";
        container.style.boxShadow = "0 2px 5px rgba(0,0,0,0.1)";
        
        container.innerHTML = `<h2>📅 ${date} のシフト</h2><canvas id="chart_${idx}"></canvas>`;
        chartsDiv.appendChild(container);

        const ctx = document.getElementById(`chart_${idx}`).getContext("2d");
        const chartDataPoints = [];
        const yAxisLabels = [];

        Object.entries(userShifts).forEach(([userId, shifts]) => {
            if (!colors[userId]) {
                colors[userId] = baseColors[colorIndex % baseColors.length];
                colorIndex++;
            }
            if (!yAxisLabels.includes(userId)) yAxisLabels.push(userId);

            shifts.forEach((s) => {
                const start = new Date(`1970-01-01T${s.start_time}:00`);
                const end = new Date(`1970-01-01T${s.end_time}:00`);
                chartDataPoints.push({
                    x: [start, end],
                    y: userId,
                    userLabel: userId,
                    type: s.type,
                    backgroundColor: s.type === "break" ? "rgba(255, 180, 80, 0.9)" : colors[userId]
                });
            });
        });

        chartDataPoints.sort((a, b) => yAxisLabels.indexOf(a.userLabel) - yAxisLabels.indexOf(b.userLabel));

        new Chart(ctx, {
            type: "bar",
            data: {
                datasets: [{
                    data: chartDataPoints,
                    backgroundColor: chartDataPoints.map(d => d.backgroundColor),
                    borderColor: "rgba(0,0,0,0.1)", borderWidth: 1
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                scales: {
                    x: {
                        type: "time",
                        time: { unit: "hour", displayFormats: { hour: "HH:mm" } },
                        min: minTime, max: maxTime
                    },
                    y: { type: 'category', labels: yAxisLabels, reverse: true }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: c => {
                                const d = c.raw;
                                const st = d.x[0].toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
                                const en = d.x[1].toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
                                return `${d.userLabel}: ${st}〜${en}`;
                            }
                        }
                    }
                }
            }
        });
    });

    // --- 合計時間グラフ ---
    const totalHoursByUser = {};
    validData.forEach(s => {
        if (s.type !== 'work') return;
        const start = new Date(`1970-01-01T${s.start_time}:00`);
        const end = new Date(`1970-01-01T${s.end_time}:00`);
        const diff = (end - start) / (1000 * 60 * 60);
        totalHoursByUser[s.user_id] = (totalHoursByUser[s.user_id] || 0) + diff;
    });

    const userLabels = Object.keys(totalHoursByUser);
    if (userLabels.length > 0) {
        const totalDiv = document.createElement("div");
        totalDiv.classList.add("chart-container");
        totalDiv.style.marginTop = "30px";
        totalDiv.style.padding = "10px";
        totalDiv.style.background = "#fff";
        totalDiv.innerHTML = `<h2>⚖️ 全体の勤務時間バランス</h2><canvas id="total_hours_chart"></canvas>`;
        chartsDiv.appendChild(totalDiv);

        new Chart(document.getElementById("total_hours_chart"), {
            type: "bar",
            data: {
                labels: userLabels,
                datasets: [{
                    label: "合計時間(H)",
                    data: userLabels.map(u => totalHoursByUser[u]),
                    backgroundColor: "rgba(54, 162, 235, 0.7)"
                }]
            },
            options: {
                responsive: true,
                scales: { y: { beginAtZero: true } }
            }
        });
    }
});