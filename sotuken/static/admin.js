document.addEventListener('DOMContentLoaded', function() {
// --- カレンダー初期化 ---
const calendarEl = document.getElementById('calendar');
const calendar = new FullCalendar.Calendar(calendarEl, {
    initialView: 'dayGridMonth',
    locale: 'ja',
    height: 'auto',
    events: '/makeshift/events',  // Flask側から取得
    eventColor: '#3B82F6',
    eventDisplay: 'block',
    eventClick: function(info) {
    alert(info.event.title + "： " + info.event.startStr + "〜" + info.event.endStr);
    }
});
calendar.render();

// --- シフト作成ボタン処理 ---
document.getElementById('make-shift-btn').addEventListener('click', async () => {
    if (!confirm("AIで新しいシフトを作成しますか？")) return;
    const res = await fetch('/makeshift/generate', { method: 'POST' });
    const data = await res.json();
    if (data.status === 'ok') {
    alert('シフトを作成しました！');
    calendar.refetchEvents(); // カレンダー更新
    } else {
    alert('シフト作成に失敗しました。');
    }
});
});
