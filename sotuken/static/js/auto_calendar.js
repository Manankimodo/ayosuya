// auto_calendar.js の内容全体を IIFE でラップする
(function() {

    // 🚨 解決コード: Date Adapterを手動でChart.jsに登録する
    // これにより、アダプターのロードがうまくいかない環境でのエラーを防ぎます。
    if (typeof Chart !== 'undefined' && typeof ChartjsAdapterDateFns === 'object') {
        // ChartjsAdapterDateFnsはロード時にグローバルに登録されると期待される変数
        try {
            Chart.register(ChartjsAdapterDateFns); 
        } catch (e) {
            console.warn("Chart.jsアダプター登録時にエラーが発生しましたが、続行します:", e);
        }
    }

    const shiftData = window.SHIFT_DATA;
    const settings = window.SETTINGS_DATA;
    
    // Y軸の表示範囲を設定から取得
    const START_TIME_DEFAULT = "08:00";
    const END_TIME_DEFAULT = "19:00";

    const startTimeStr = settings && settings.start_time ? settings.start_time : START_TIME_DEFAULT;
    const endTimeStr = settings && settings.end_time ? settings.end_time : END_TIME_DEFAULT;
    
    let minTime = new Date(`1970-01-01T${startTimeStr}:00`);
    let maxTime = new Date(`1970-01-01T${endTimeStr}:00`);


    // 🚨 ガード句: shiftData が undefined だった場合、処理を中断
    if (!shiftData || !Array.isArray(shiftData)) {
        console.error("致命的なエラー: shiftData が配列として取得できませんでした。");
        const chartsDiv = document.getElementById("charts");
        if (chartsDiv) {
            chartsDiv.innerHTML = "<p>データ読み込みエラー。シフト情報がサーバーから渡されていません。</p>";
        }
        return; 
    }

    // データが有効であることが確認されたので、安全に filter を実行
    const validData = shiftData.filter(s => s.start_time && s.end_time);

    if (validData.length === 0) {
        document.getElementById("charts").innerHTML = "<p>有効なシフトがありません。</p>";
    } else {
        const groupedByDateAndUser = {};
        
        validData.forEach(s => {
            const date = s.date;
            const userId = s.user_id;
            
            if (!groupedByDateAndUser[date]) groupedByDateAndUser[date] = {};
            if (!groupedByDateAndUser[date][userId]) groupedByDateAndUser[date][userId] = [];
            
            groupedByDateAndUser[date][userId].push(s);
        });

        const chartsDiv = document.getElementById("charts");
        
        const colors = {};
        let colorIndex = 0;
        const baseColors = ["hsl(0, 70%, 60%)", "hsl(70, 70%, 60%)", "hsl(140, 70%, 60%)", "hsl(210, 70%, 60%)", "hsl(280, 70%, 60%)"];

        // =========================================================================
        // 1. 日付別ガントチャート ＋ 人数過不足グラフの描画ループ
        // =========================================================================
        Object.entries(groupedByDateAndUser).forEach(([date, userShifts], idx) => {
            
            // --- ガントチャートの描画領域 ---
            const container = document.createElement("div");
            container.classList.add("chart-container");
            container.innerHTML = `<h2>📅 ${date} のシフト（ガントチャート）</h2><canvas id="chart_${idx}"></canvas>`;
            chartsDiv.appendChild(container);

            const ctx = document.getElementById(`chart_${idx}`).getContext("2d");
            
            const chartDataPoints = []; 
            const yAxisLabels = []; 

            // 🚨 人数カウントのためのデータ準備 (ガントチャートデータ収集と同時に行う)
            const intervalMinutes = 30; // 30分間隔で集計
            const maxPeople = settings && settings.max_people_per_shift ? settings.max_people_per_shift : 5; // 必要人数 (デフォルト5)
            
            const timePoints = [];
            let currentTime = new Date(minTime);
            while (currentTime <= maxTime) {
                timePoints.push(new Date(currentTime));
                currentTime.setMinutes(currentTime.getMinutes() + intervalMinutes);
            }
            if (timePoints[timePoints.length - 1].getTime() !== maxTime.getTime()) {
                timePoints.push(new Date(maxTime));
            }
            
            const actualPeopleCount = new Array(timePoints.length - 1).fill(0); 

            // --- シフトデータの処理 ---
            Object.entries(userShifts).forEach(([userId, shifts]) => {
                // ユーザーIDに色を割り当て
                if (!colors[userId]) {
                    colors[userId] = baseColors[colorIndex % baseColors.length];
                    colorIndex++;
                }
                const userColor = colors[userId];
                
                if (!yAxisLabels.includes(userId)) {
                    yAxisLabels.push(userId);
                }

                shifts.forEach((s) => {
                    const start = new Date(`1970-01-01T${s.start_time}:00`);
                    const end = new Date(`1970-01-01T${s.end_time}:00`);
                    
                    if (isNaN(start.getTime()) || isNaN(end.getTime())) {
                        console.warn(`無効な時間データが見つかりました: ${s.user_id} の ${s.date}`);
                        return;
                    }

                    const isBreak = s.type === "break";
                    
                    chartDataPoints.push({
                        x: [start, end], 
                        y: userId, 
                        userLabel: userId,
                        type: s.type,
                        backgroundColor: isBreak ? "rgba(255, 180, 80, 0.9)" : userColor
                    });

                    // 🚨 人数カウント
                    if (s.type === 'work') {
                        const shiftStart = start.getTime();
                        const shiftEnd = end.getTime();
                        for (let i = 0; i < timePoints.length - 1; i++) {
                            const intervalStart = timePoints[i].getTime();
                            const intervalEnd = timePoints[i+1].getTime();
                            
                            if (shiftStart < intervalEnd && shiftEnd > intervalStart) {
                                actualPeopleCount[i]++;
                            }
                        }
                    }
                });
            });

            // 🎯 ガントチャートの描画
            chartDataPoints.sort((a, b) => {
                return yAxisLabels.indexOf(a.userLabel) - yAxisLabels.indexOf(b.userLabel);
            });

            new Chart(ctx, {
                type: "bar",
                data: { datasets: [{
                    label: "勤務・休憩",
                    data: chartDataPoints,
                    backgroundColor: chartDataPoints.map(d => d.backgroundColor),
                    borderColor: "rgba(0,0,0,0.2)",
                    borderWidth: 1,
                    barPercentage: 0.8,
                    categoryPercentage: 0.9,
                }]
                },
                options: {
                    indexAxis: "y",
                    responsive: true,
                    scales: {
                        x: {
                            type: "time",
                            time: { unit: "hour", displayFormats: { hour: "HH:mm" } },
                            min: minTime, max: maxTime, 
                            title: { display: true, text: "時間" }
                        },
                        y: { 
                            type: 'category', 
                            labels: yAxisLabels, reverse: true, 
                            grid: { display: true },
                            title: { display: true, text: "スタッフ ID" } 
                        }
                    },
                    plugins: {
                        legend: { display: false }, 
                        tooltip: {
                            callbacks: {
                                label: ctx => {
                                    const rawData = ctx.raw;
                                    const start = new Date(rawData.x[0]).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
                                    const end = new Date(rawData.x[1]).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
                                    const type = rawData.type === "break" ? "休憩" : "勤務";
                                    return `${rawData.userLabel} (${type}): ${start}〜${end}`;
                                }
                            }
                        }
                    }
                }
            });

            // -------------------------------------------------------------------------
            // 🎯 人数過不足グラフ (Line Chart) の描画
            // -------------------------------------------------------------------------

            const lineContainer = document.createElement("div");
            lineContainer.classList.add("chart-container");
            lineContainer.innerHTML = `<h3>📊 ${date} の人数過不足分析</h3><canvas id="line_chart_${idx}"></canvas>`;
            chartsDiv.appendChild(lineContainer);

            const lineCtx = document.getElementById(`line_chart_${idx}`).getContext("2d");
            const chartLabels = timePoints.slice(0, -1).map(t => t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));

            new Chart(lineCtx, {
                type: 'line',
                data: {
                    labels: chartLabels,
                    datasets: [
                        {
                            label: '実働人数',
                            data: actualPeopleCount,
                            borderColor: 'rgba(54, 162, 235, 1)',
                            backgroundColor: 'rgba(54, 162, 235, 0.2)',
                            fill: true, tension: 0.1,
                        },
                        {
                            label: `必要人数 (${maxPeople}人)`,
                            data: new Array(actualPeopleCount.length).fill(maxPeople),
                            borderColor: 'rgba(255, 99, 132, 1)',
                            backgroundColor: 'rgba(255, 99, 132, 0.1)',
                            borderDash: [5, 5], fill: false, tension: 0.1,
                        }
                    ]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: '人数 (人)' },
                            suggestedMax: Math.max(...actualPeopleCount, maxPeople) + 1,
                            ticks: { stepSize: 1 }
                        },
                        x: { title: { display: true, text: '時間帯' } }
                    },
                    plugins: {
                        title: { display: true, text: '時間帯別 実働人数 vs 必要人数' }
                    }
                }
            });
        });
        
        // =========================================================================
        // 2. ユーザー別合計勤務時間グラフ
        // =========================================================================
        const totalHoursByUser = {};

        validData.forEach(s => {
            if (s.type !== 'work') return; 

            const start = new Date(`1970-01-01T${s.start_time}:00`);
            const end = new Date(`1970-01-01T${s.end_time}:00`);
            
            if (isNaN(start.getTime()) || isNaN(end.getTime())) return; 

            const durationMinutes = (end - start) / (1000 * 60); 

            const userId = s.user_id;
            if (!totalHoursByUser[userId]) {
                totalHoursByUser[userId] = 0;
            }
            totalHoursByUser[userId] += durationMinutes;
        });

        const userLabels = Object.keys(totalHoursByUser);
        const totalHoursData = userLabels.map(userId => totalHoursByUser[userId] / 60); 

        if (userLabels.length > 0) {
            const totalChartContainer = document.createElement("div");
            totalChartContainer.classList.add("chart-container", "total-chart");
            totalChartContainer.innerHTML = `<h2>⚖️ 全体の合計勤務時間バランス</h2><canvas id="total_hours_chart"></canvas>`;
            chartsDiv.appendChild(totalChartContainer);

            const totalCtx = document.getElementById("total_hours_chart").getContext("2d");

            new Chart(totalCtx, {
                type: "bar",
                data: {
                    labels: userLabels,
                    datasets: [{
                        label: "合計勤務時間（時間）",
                        data: totalHoursData,
                        backgroundColor: 'rgba(54, 162, 235, 0.8)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        x: { title: { display: true, text: "スタッフ ID" } },
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: "合計勤務時間 (H)" },
                        }
                    },
                    plugins: {
                        legend: { display: false },
                        title: { display: true, text: '各スタッフの合計勤務時間' }
                    }
                }
            });
        }
    }
})(); // IIFE の終了