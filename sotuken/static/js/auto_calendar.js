// ==========================================
// 4. ハンバーガーメニュー制御
// ==========================================
document.addEventListener("DOMContentLoaded", function() {
    const menuBtn = document.getElementById('menuBtn');
    const sideMenu = document.getElementById('sideMenu');

    if (menuBtn && sideMenu) {
        menuBtn.addEventListener('click', function() {
            menuBtn.classList.toggle('active');
            sideMenu.classList.toggle('active');
        });
        
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
// 🎨 Chart.js 設定
// ==========================================
Chart.defaults.color = '#000000';
Chart.defaults.borderColor = '#dddddd';
Chart.defaults.font.family = '"Helvetica Neue", "Arial", sans-serif';

// ==========================================
// ヘルプ募集機能
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
    // (省略: 変更なし)
    alert("機能未実装です");
    closeHelpModal();
}

window.onclick = function(event) {
    const modal = document.getElementById('helpModal');
    if (event.target == modal) closeHelpModal();
}

// ==========================================
// ★★★ メイン：グラフ描画ロジック ★★★
// ==========================================
document.addEventListener("DOMContentLoaded", function() {
    const rawData = window.flaskData.shifts || [];
    const settings = window.flaskData.settings || {};
    const chartsDiv = document.getElementById("charts");
    
    if (!rawData || rawData.length === 0 || !chartsDiv) return;

    // 1. データをソートする（結合処理のために必須）
    // ユーザーID順 -> 日付順 -> 開始時間順
    rawData.sort((a, b) => {
        if (a.user_id !== b.user_id) return a.user_id - b.user_id;
        if (a.date !== b.date) return a.date.localeCompare(b.date);
        return a.start_time.localeCompare(b.start_time);
    });

    // 2. ▼▼▼ ここが魔法の結合ロジック ▼▼▼
    // 15分刻みのバラバラなデータを、連続していれば1つにまとめる
    const mergedShifts = [];
    if (rawData.length > 0) {
        // 最初のデータをセット
        // ※オブジェクトのコピーを作る (参照渡しを防ぐため)
        let current = { ...rawData[0] }; 

        for (let i = 1; i < rawData.length; i++) {
            const next = rawData[i];

            // 「同じ人」かつ「同じ日」かつ「同じ役割」かつ「時間が連続している」なら結合
            if (current.user_id === next.user_id &&
                current.date === next.date &&
                current.type === next.type &&
                current.end_time === next.start_time) {
                
                // 終了時間を延長する
                current.end_time = next.end_time;
            } else {
                // 連続していないなら、今のデータを保存して次へ
                mergedShifts.push(current);
                current = { ...next };
            }
        }
        // 最後のデータを保存
        mergedShifts.push(current);
    }
    // ▲▲▲ 結合ロジック終わり ▲▲▲


    // 3. 時間設定
    const minTime = settings.start_time ? new Date(`1970-01-01T${settings.start_time}:00`) : new Date("1970-01-01T08:00:00");
    const maxTime = settings.end_time ? new Date(`1970-01-01T${settings.end_time}:00`) : new Date("1970-01-01T22:00:00");

    // 4. データを日付ごとにグループ化
    const groupedByDate = {};
    mergedShifts.forEach(s => {
        if (!groupedByDate[s.date]) groupedByDate[s.date] = [];
        groupedByDate[s.date].push(s);
    });

    const baseColors = ["hsl(0, 70%, 60%)", "hsl(70, 70%, 60%)", "hsl(140, 70%, 60%)", "hsl(210, 70%, 60%)", "hsl(280, 70%, 60%)"];
    const userColorMap = {};
    let colorIndex = 0;

    // 5. グラフ生成ループ
    Object.entries(groupedByDate).forEach(([date, shifts], idx) => {
        const container = document.createElement("div");
        container.className = "chart-container";
        // CSS調整
        container.style.marginBottom = "30px";
        container.style.padding = "15px";
        container.style.background = "#fff";
        container.style.borderRadius = "8px";
        container.style.boxShadow = "0 2px 5px rgba(0,0,0,0.1)";

        container.innerHTML = `<h3>📅 ${date} のシフト</h3><div style="height: 400px;"><canvas id="chart_${idx}"></canvas></div>`;
        chartsDiv.appendChild(container);

        const ctx = document.getElementById(`chart_${idx}`).getContext("2d");
        
        // Y軸のラベル（ユーザー名）を収集
        const yLabels = [...new Set(shifts.map(s => s.user_name || `ID:${s.user_id}`))];

        // データポイント作成
        const chartDataPoints = shifts.map(s => {
            const uName = s.user_name || `ID:${s.user_id}`;
            
            // ユーザーごとの色決定
            if (!userColorMap[s.user_id]) {
                userColorMap[s.user_id] = baseColors[colorIndex % baseColors.length];
                colorIndex++;
            }
            
            // 役割に応じた色上書き (任意)
            let barColor = userColorMap[s.user_id];
            if (s.type === "キッチン") barColor = "#e57373"; // 赤
            if (s.type === "ホール") barColor = "#64b5f6";   // 青

            return {
                x: [new Date(`1970-01-01T${s.start_time}:00`), new Date(`1970-01-01T${s.end_time}:00`)],
                y: uName,
                type: s.type,
                backgroundColor: barColor
            };
        });

        new Chart(ctx, {
            type: "bar",
            data: {
                datasets: [{
                    data: chartDataPoints,
                    backgroundColor: chartDataPoints.map(d => d.backgroundColor),
                    // 棒の太さ設定
                    barPercentage: 0.8, 
                    categoryPercentage: 0.9,
                    borderSkipped: false, // 枠線を全周に
                    borderRadius: 4 // 角を少し丸く
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: "time",
                        time: { unit: "hour", displayFormats: { hour: "HH:mm" } },
                        min: minTime, max: maxTime,
                        grid: { color: "#eee" }
                    },
                    y: { 
                        type: 'category', 
                        labels: yLabels,
                        grid: { color: "#eee" }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: c => {
                                const d = c.raw;
                                const st = d.x[0].toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
                                const en = d.x[1].toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
                                return `${d.type}: ${st}〜${en}`;
                            }
                        }
                    },
                    // バーの中に文字を表示するカスタムプラグイン
                    // (JSの最後に定義しても良いですが、ここでは簡易的に)
                }
            },
            plugins: [{
                id: 'roleLabels',
                afterDatasetsDraw(chart) {
                    const { ctx } = chart;
                    chart.data.datasets.forEach((dataset, i) => {
                        const meta = chart.getDatasetMeta(i);
                        if (!meta.hidden) {
                            meta.data.forEach((element, index) => {
                                const d = dataset.data[index];
                                if (d.type && d.type !== 'work') {
                                    ctx.fillStyle = '#fff'; // 文字色（白）
                                    ctx.font = 'bold 12px Arial';
                                    ctx.textAlign = 'center';
                                    ctx.textBaseline = 'middle';
                                    ctx.shadowColor = 'rgba(0, 0, 0, 0.5)';
                                    ctx.shadowBlur = 3;
                                    ctx.fillText(d.type, element.x, element.y);
                                    ctx.shadowBlur = 0; // 影リセット
                                }
                            });
                        }
                    });
                }
            }]
        });
    });
});