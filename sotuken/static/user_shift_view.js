
// Flaskから渡されたログイン中のユーザーID
const userId = "{{ user_id }}"; 
const shiftContainer = document.getElementById('shift-container');

async function fetchShifts() {
    try {
        // ★ 変更点1: 全シフト取得APIを呼び出す ★
        const response = await fetch(`/makeshift/api/shifts/all`);
        
        if (!response.ok) {
            throw new Error(`HTTPエラー: ${response.status}`);
        }
        
        const data = await response.json();
        
        // 取得した全シフトを日付ごとにグルーピング
        const groupedShifts = groupShiftsByDate(data.shifts);
        
        renderShifts(groupedShifts);

    } catch (error) {
        console.error("シフトデータの取得に失敗しました:", error);
        shiftContainer.innerHTML = `<p class="error">エラーが発生しました: シフトを読み込めません。</p>`;
    }
}

// データを日付ごとにグルーピングするヘルパー関数
function groupShiftsByDate(shifts) {
    const grouped = {};
    shifts.forEach(shift => {
        const date = shift.date;
        if (!grouped[date]) {
            grouped[date] = [];
        }
        grouped[date].push(shift);
    });
    // 日付でソート
    return Object.keys(grouped).sort().reduce((obj, key) => {
        obj[key] = grouped[key];
        return obj;
    }, {});
}

function renderShifts(groupedShifts) {
    shiftContainer.innerHTML = ''; // ローディングメッセージをクリア

    const dates = Object.keys(groupedShifts);

    if (dates.length === 0) {
        shiftContainer.innerHTML = '<p style="text-align: center; color: #6c757d;">現在、確定しているシフトはありません。</p>';
        return;
    }

    const ul = document.createElement('ul');
    ul.className = 'shift-list';
    
    dates.forEach(date => {
        const shiftsOfDay = groupedShifts[date];
        
        // --- 日付ヘッダー ---
        const dateHeader = document.createElement('div');
        dateHeader.className = 'shift-date-header';
        dateHeader.innerHTML = `<h3>📅 ${date}</h3>`;
        ul.appendChild(dateHeader);
        
        // --- その日のシフト一覧 ---
        shiftsOfDay
            .filter(shift => shift.type === 'work') // 'work'タイプのみ表示
            .forEach(shift => {
            
            const li = document.createElement('li');
            li.className = 'shift-item';

            // 自分のシフトは強調表示
            const isCurrentUser = String(shift.user_id) === String(userId);
            if (isCurrentUser) {
                // 自分のシフトは分かりやすいようにスタイルを上書き
                li.style.borderLeftColor = '#28a745'; 
                li.style.backgroundColor = '#e6ffed';
            }
            
            const time_display = shift.start_time && shift.end_time ? 
                                `${shift.start_time} - ${shift.end_time}` : 
                                '時間未定';
            
            // ★ 変更点2: ユーザー名と時間を表示 ★
            li.innerHTML = `
                <p><strong>${shift.user_name}</strong>: ${time_display} ${isCurrentUser ? ' (あなた)' : ''}</p>
            `;
            ul.appendChild(li);
        });
        
        // 日付の区切り線
        const hr = document.createElement('hr');
        hr.style.margin = '20px 0';
        ul.appendChild(hr);

    });

    shiftContainer.appendChild(ul);
}
// 🍔 ハンバーガーメニュー動作
const hamburger = document.getElementById('hamburger');
const menu = document.getElementById('menu');

hamburger.addEventListener('click', () => {
    // activeクラスをトグル
    hamburger.classList.toggle('active');
    menu.classList.toggle('active');
});

// 🔹 ログアウト確認アラート (必要であれば)
const logoutLink = document.getElementById("logout-link-confirm");
if (logoutLink) {
    logoutLink.addEventListener("click", function (e) {
        e.preventDefault();
        const confirmed = confirm("ログアウトしますか？");
        if (confirmed) {
            // ⚠️ ログアウトURLを適宜修正してください
            window.location.href = "{{ url_for('login.logout') }}"; 
        }
    });
}

fetchShifts();

