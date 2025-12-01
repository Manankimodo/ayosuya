// user_shift_view.js

// ユーザーIDの取得 (HTMLのpタグから取得)
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
function getWeekStartDate(dateStr) {
    // ★修正: 文字列 "YYYY-MM-DD" から Date オブジェクトを作成
    // UTC解釈を避けるため、split して構築
    const parts = dateStr.split('-');
    const d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
    d.setHours(0, 0, 0, 0);
    
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
    
    console.log('🔍 グループ化されたシフト:', grouped);
    return grouped;
}

// 取得した全ての日付を週ごとに分割
function generateDatesByWeek(dates) {
    console.log('📅 処理対象の日付:', dates);
    
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
    
    console.log('📊 週ごとの日付配列:', datesByWeek);

    // ★修正: 初期表示を「最初の週」に設定
    // 「今日」を含む週を探すが、見つからない場合は最初の週から開始
    const today = formatDate(new Date());
    console.log('📆 今日の日付:', today);
    
    currentWeekIndex = 0; // デフォルトは最初の週
    for (let i = 0; i < datesByWeek.length; i++) {
        if (datesByWeek[i].includes(today)) {
            currentWeekIndex = i;
            console.log(`✅ 今日を含む週が見つかりました (インデックス: ${i})`);
            break;
        }
    }
    
    if (currentWeekIndex === 0) {
        console.log('⚠️ 今日を含む週が見つかりません。最初の週から開始します');
    }
}


// === メインロジック (データ取得) ===

async function fetchShifts() {
    try {
        console.log(`🚀 ユーザーID: ${userId} のシフトを取得中...`);
        
        // ユーザーIDが取得できているか確認
        if (!userId) {
            throw new Error('ユーザーIDが見つかりません');
        }
        
        const response = await fetch(`/makeshift/api/shifts/user/${userId}`); 
        
        if (!response.ok) {
            throw new Error(`HTTPエラー: ${response.status}`);
        }
        
        const data = await response.json();
        
        console.log('📥 APIレスポンス:', data);
        
        const shiftsArray = data.shifts || [];
        
        console.log(`📊 受け取ったシフト件数: ${shiftsArray.length}`);
        
        // ★修正: 負のuser_idを除外
        const validShifts = shiftsArray.filter(shift => {
            const uid = parseInt(shift.user_id);
            const isValid = uid > 0;
            if (!isValid) {
                console.log(`⚠️ 負のIDをフィルタ: ${shift.user_id}`);
            }
            return isValid;
        });
        
        console.log(`✅ フィルタ後のシフト件数: ${validShifts.length}`);
        
        if (validShifts.length === 0) {
            shiftContainer.innerHTML = '<p style="text-align: center; color: #6c757d;">現在、確定しているシフトはありません。</p>';
            currentWeekRange.textContent = 'データなし';
            attachEventListeners();
            return;
        }
        
        allGroupedShifts = groupShiftsByDate(validShifts);
        
        const uniqueDates = Array.from(new Set(validShifts.map(s => s.date)));
        console.log(`📌 ユニークな日付: ${uniqueDates.length}件`);
        
        generateDatesByWeek(uniqueDates);
        
        if (datesByWeek.length === 0) {
            throw new Error('週データの生成に失敗しました');
        }
        
        displayCurrentWeekShifts(); // 初回表示
        
        attachEventListeners(); // イベントリスナー登録

    } catch (error) {
        console.error("❌ シフトデータの取得に失敗しました:", error);
        shiftContainer.innerHTML = `<p class="error" style="text-align: center; color: #dc3545;">エラーが発生しました: ${error.message}</p>`;
        currentWeekRange.textContent = 'エラー';
        attachEventListeners();
    }
}

// === シフト表示ロジック ===

function displayCurrentWeekShifts() {
    console.log(`📺 現在の週インデックス: ${currentWeekIndex}`);
    
    if (datesByWeek.length === 0) {
         shiftContainer.innerHTML = '<p style="text-align: center; color: #6c757d;">現在、確定しているシフトはありません。</p>';
        currentWeekRange.textContent = 'データなし';
        return;
    }

    const currentWeekDates = datesByWeek[currentWeekIndex];
    console.log(`📅 表示対象の週の日付: ${currentWeekDates}`);
    
    const weekStartObj = getWeekStartDate(currentWeekDates[0]); 
    
    const weekEndObj = new Date(weekStartObj);
    weekEndObj.setDate(weekEndObj.getDate() + 6);

    const firstDateStr = formatDate(weekStartObj);
    const lastDateStr = formatDate(weekEndObj);

    // 週の範囲を更新 (月曜〜日曜を表示)
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

    console.log(`📆 表示対象の7日間: ${displayDates}`);

    displayDates.forEach(date => {
        const shiftsOfDay = allGroupedShifts[date] || []; 
        
        // --- 日付ヘッダー ---
        const dateHeader = document.createElement('div');
        dateHeader.className = 'shift-date-header';
        dateHeader.innerHTML = `<h3>📅 ${formatDisplayDate(date)}</h3>`;
        ul.appendChild(dateHeader);
        
        // --- その日のシフト一覧 ---
        const validShiftsOfDay = shiftsOfDay.filter(shift => {
            const uid = parseInt(shift.user_id);
            return uid > 0; // 負のIDを除外
        });

        if (validShiftsOfDay.length === 0) {
             const emptyLi = document.createElement('li');
             emptyLi.className = 'shift-item';
             emptyLi.innerHTML = `<p style="color: #6c757d;">出勤者なし</p>`;
             ul.appendChild(emptyLi);
        } else {
            validShiftsOfDay.forEach(shift => {
                const li = document.createElement('li');
                li.className = 'shift-item';

                // 自分のシフトを強調表示
                const isCurrentUser = String(shift.user_id) === String(userId);
                if (isCurrentUser) {
                    li.classList.add('current-user-shift');
                    console.log(`✨ 自分のシフト: ${shift.user_name} (${shift.start_time} - ${shift.end_time})`);
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
}


// === ログアウト確認アラート (既存のコードを維持) ===
const logoutLink = document.getElementById("logout-link");
if (logoutLink) {
    logoutLink.addEventListener("click", function (e) {
        e.preventDefault(); 
        
        // data属性からログアウトURLを取得
        const logoutUrl = this.getAttribute('data-logout-url');
        
        if (!logoutUrl) {
            console.error("ログアウトURLが見つかりません。");
            return;
        }
        
        const confirmed = confirm("ログアウトしますか？");
        if (confirmed) {
            // 取得したURLを使用
            window.location.href = logoutUrl;
        }
    });
}

console.log('🎬 user_shift_view.js 読み込み完了');
fetchShifts();