// user_shift_view.js

// ユーザーIDの取得 (HTMLのpタグから取得する暫定ロジックを維持)
const userIdElement = document.querySelector('.header p');
const userId = userIdElement ? userIdElement.textContent.replace('ユーザーID: ', '').trim() : '';

const shiftContainer = document.getElementById('shift-container');
const prevWeekBtn = document.getElementById('prevWeek');
const nextWeekBtn = document.getElementById('nextWeek');
const currentWeekRange = document.getElementById('currentWeekRange');

let allGroupedShifts = {}; // 全シフトデータ (日付でグループ化済み)
let datesByWeek = [];     // 週ごとの日付配列
let currentWeekIndex = 0; // 現在表示している週のインデックス


// --- ユーティリティ関数 ---

// 週の開始日（月曜日）を取得 (ISO 8601準拠)
function getWeekStartDate(date) {
    const d = new Date(date);
    d.setHours(0, 0, 0, 0); // 時刻をリセット
    
    // 0:日曜, 1:月曜, ..., 6:土曜
    let day = d.getDay(); 
    
    // 月曜を0日目とするために調整
    let dayOfWeek = day === 0 ? 6 : day - 1; 

    // 現在の日付から、週の開始日（月曜日）までの日数を引く
    d.setDate(d.getDate() - dayOfWeek);
    
    return d;
}

// Dateオブジェクトを YYYY-MM-DD 形式にフォーマット
function formatDate(dateObj) {
    const y = dateObj.getFullYear();
    const m = String(dateObj.getMonth() + 1).padStart(2, '0');
    const d = String(dateObj.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
}

// 日付を MM/DD 形式で表示用にフォーマット
function formatDisplayDate(dateStr) {
    const parts = dateStr.split('-');
    return `${parts[1]}/${parts[2]}`;
}

// シフトデータを日付ごとにグルーピング
function groupShiftsByDate(shifts) {
    const grouped = {};
    shifts.forEach(shift => {
        const date = shift.date;
        if (!grouped[date]) {
            grouped[date] = [];
        }
        grouped[date].push(shift);
    });
    return grouped;
}

// 取得した全ての日付を週ごとに分割
function generateDatesByWeek(dates) {
    if (dates.length === 0) return;
    dates.sort();
    
    const weekMap = new Map();
    dates.forEach(dateStr => {
        const weekStart = getWeekStartDate(dateStr);
        const weekStartStr = formatDate(weekStart);
        if (!weekMap.has(weekStartStr)) {
            weekMap.set(weekStartStr, []);
        }
        weekMap.get(weekStartStr).push(dateStr);
    });

    // 週の開始日でソートして配列化
    datesByWeek = Array.from(weekMap.keys()).sort().map(key => weekMap.get(key));

    // 初期表示を「今日」が含まれる週に設定
    const today = formatDate(new Date());
    currentWeekIndex = datesByWeek.findIndex(week => week.includes(today));
    if (currentWeekIndex === -1) {
        currentWeekIndex = 0;
    }
}


// === メインロジック (データ取得) ===

async function fetchShifts() {
    try {
        const response = await fetch(`/makeshift/api/shifts/all`);
        
        if (!response.ok) {
            throw new Error(`HTTPエラー: ${response.status}`);
        }
        
        const data = await response.json();
        
        allGroupedShifts = groupShiftsByDate(data.shifts);
        
        const uniqueDates = Array.from(new Set(data.shifts.map(s => s.date)));
        
        generateDatesByWeek(uniqueDates);
        
        displayCurrentWeekShifts(); // 初回表示
        
        attachEventListeners(); // イベントリスナー登録

    } catch (error) {
        console.error("シフトデータの取得に失敗しました:", error);
        shiftContainer.innerHTML = `<p class="error">エラーが発生しました: シフトを読み込めません。</p>`;
        currentWeekRange.textContent = 'エラー';
    }
}

// === シフト表示ロジック ===

function displayCurrentWeekShifts() {
    if (datesByWeek.length === 0) {
         shiftContainer.innerHTML = '<p style="text-align: center; color: #6c757d;">現在、確定しているシフトはありません。</p>';
        currentWeekRange.textContent = 'データなし';
        return;
    }

    const currentWeekDates = datesByWeek[currentWeekIndex];
    
    // ★ 修正1: 週の開始日（月曜日）を正確に計算
    const weekStartObj = getWeekStartDate(currentWeekDates[0]); 
    
    // ★ 修正2: 週の最終日（日曜日）を計算 (開始日の6日後)
    const weekEndObj = new Date(weekStartObj);
    weekEndObj.setDate(weekEndObj.getDate() + 6);

    const firstDateStr = formatDate(weekStartObj);
    const lastDateStr = formatDate(weekEndObj);

    // 週の範囲を更新 (データに関わらず、月曜〜日曜を表示)
    currentWeekRange.textContent = `${formatDisplayDate(firstDateStr)} 〜 ${formatDisplayDate(lastDateStr)}`;

    const ul = document.createElement('ul');
    ul.className = 'shift-list';
    shiftContainer.innerHTML = ''; // クリア

    // 月曜日から日曜日までの7日間の日付配列を作成
    const displayDates = [];
    for (let i = 0; i < 7; i++) {
        const d = new Date(weekStartObj);
        d.setDate(d.getDate() + i);
        displayDates.push(formatDate(d));
    }

    displayDates.forEach(date => {
        const shiftsOfDay = allGroupedShifts[date] || []; // データがない日(shiftsOfDay=[]となる)も処理
        
        // --- 日付ヘッダー ---
        const dateHeader = document.createElement('div');
        dateHeader.className = 'shift-date-header';
        dateHeader.innerHTML = `<h3>📅 ${formatDisplayDate(date)}</h3>`;
        ul.appendChild(dateHeader);
        
        // --- その日のシフト一覧 ---
        const workShifts = shiftsOfDay.filter(shift => shift.type === 'work');

        if (workShifts.length === 0) {
             const emptyLi = document.createElement('li');
             emptyLi.className = 'shift-item';
             emptyLi.innerHTML = `<p style="color: #6c757d;">出勤者なし</p>`;
             ul.appendChild(emptyLi);
        } else {
            workShifts.forEach(shift => {
                const li = document.createElement('li');
                li.className = 'shift-item';

                // 自分のシフトを強調表示
                const isCurrentUser = String(shift.user_id) === String(userId);
                if (isCurrentUser) {
                    li.classList.add('current-user-shift');
                }
                
                const time_display = shift.start_time && shift.end_time ? 
                `${shift.start_time} - ${shift.end_time}` : 
                '時間未定';
                
                li.innerHTML = `
                    <p><strong>${shift.user_name}</strong>: ${time_display} ${isCurrentUser ? ' (あなた)' : ''}</p>
                `;
                ul.appendChild(li);
            });
        }
    });

    const hr = document.createElement('hr');
    hr.style.margin = '20px 0';
    ul.appendChild(hr);

    shiftContainer.appendChild(ul);
    updateButtonState();
}

// ボタンの活性/非活性を制御
function updateButtonState() {
    prevWeekBtn.disabled = currentWeekIndex === 0;
    nextWeekBtn.disabled = currentWeekIndex === datesByWeek.length - 1;
}

// === イベントリスナーの登録 ===

function attachEventListeners() {
    // 週切り替えボタン
    prevWeekBtn.addEventListener('click', () => {
        if (currentWeekIndex > 0) {
            currentWeekIndex--;
            displayCurrentWeekShifts();
        }
    });

    nextWeekBtn.addEventListener('click', () => {
        if (currentWeekIndex < datesByWeek.length - 1) {
            currentWeekIndex++;
            displayCurrentWeekShifts();
        }
    });
    
    // ハンバーガーメニュー
    const hamburger = document.getElementById('hamburger');
    const menu = document.getElementById('menu');

    if (hamburger && menu) {
        hamburger.addEventListener('click', () => {
            hamburger.classList.toggle('active');
            menu.classList.toggle('active');
        });
    }

    // ログアウトリンク
    const logoutLink = document.getElementById("logout-link-confirm");
    if (logoutLink) {
        logoutLink.addEventListener("click", function (e) {
            e.preventDefault();
            const confirmed = confirm("ログアウトしますか？");
            if (confirmed) {
                window.location.href = "{{ url_for('login.logout') }}"; 
            }
        });
    }
}

fetchShifts();