// user_shift_view.js (公開機能対応 & ボトムナビゲーション版)

// ユーザーIDの取得 (HTMLから取得)
const userIdElement = document.querySelector('.user-id-display');
const userId = userIdElement ? userIdElement.textContent.replace('ID: ', '').trim() : '';

const shiftContainer = document.getElementById('shift-container');
const prevWeekBtn = document.getElementById('prevWeek');
const nextWeekBtn = document.getElementById('nextWeek');
const currentWeekRange = document.getElementById('currentWeekRange');

let allGroupedShifts = {}; // 全シフトデータ (日付でグループ化済み)
let datesByWeek = [];      // 週ごとの日付配列
let currentWeekIndex = 0;  // 現在表示している週のインデックス

// ★追加: 公開済みの月リストを保存する変数
let publishedMonths = []; 

// --- ユーティリティ関数 ---

// 週の開始日（月曜日）を取得
function getWeekStartDate(dateStr) {
    const parts = dateStr.split('-');
    const d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
    d.setHours(0, 0, 0, 0);
    
    let day = d.getDay(); 
    let dayOfWeek = day === 0 ? 6 : day - 1; 

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

// 取得した全ての日付を週ごとに分割 (修正版: データがなくてもカレンダー枠を強制生成)
function generateDatesByWeek(dates) {
    // 1. 表示範囲の決定
    // デフォルトで「今日から前後2ヶ月」は必ず表示するようにする
    const today = new Date();
    const rangeStart = new Date(today);
    rangeStart.setMonth(rangeStart.getMonth() - 2); // 2ヶ月前
    
    const rangeEnd = new Date(today);
    rangeEnd.setMonth(rangeEnd.getMonth() + 2);     // 2ヶ月後（未来）

    // もしシフトデータがこの範囲外にあれば、範囲を広げる
    if (dates.length > 0) {
        dates.sort();
        const dataMin = new Date(dates[0]);
        const dataMax = new Date(dates[dates.length - 1]);
        
        if (dataMin < rangeStart) rangeStart.setTime(dataMin.getTime());
        if (dataMax > rangeEnd) rangeEnd.setTime(dataMax.getTime());
    }

    // 2. 開始日を「月曜日」に揃える
    let day = rangeStart.getDay(); 
    let dayOfWeek = day === 0 ? 6 : day - 1; 
    rangeStart.setDate(rangeStart.getDate() - dayOfWeek);
    rangeStart.setHours(0,0,0,0);

    // 3. 週ごとの配列を生成 (ループで回して埋める)
    datesByWeek = [];
    let current = new Date(rangeStart);
    
    // 終了日を超えるまで週を追加し続ける
    while (current <= rangeEnd) {
        const weekDates = [];
        for (let i = 0; i < 7; i++) {
            weekDates.push(formatDate(current)); // YYYY-MM-DD形式で追加
            current.setDate(current.getDate() + 1); // 1日進める
        }
        datesByWeek.push(weekDates);
    }
    
    console.log(`📊 カレンダー生成: ${datesByWeek.length}週間分`);

    // 4. 初期表示位置の設定（今日を含む週）
    // 強制的に今日の枠を作っているので、検索すれば必ず見つかります
    const todayStr = formatDate(today);
    currentWeekIndex = 0;
    
    for (let i = 0; i < datesByWeek.length; i++) {
        if (datesByWeek[i].includes(todayStr)) {
            currentWeekIndex = i;
            console.log(`✅ 今日を含む週を表示: ${todayStr}`);
            break; 
        }
    }
}

// === メインロジック (データ取得) ===

async function fetchShifts() {
    try {
        console.log(`🚀 ユーザーID: ${userId} のシフトを取得中...`);
        
        if (!userId) {
            throw new Error('ユーザーIDが見つかりません');
        }
        
        const response = await fetch(`/makeshift/api/shifts/user/${userId}`); 
        
        if (!response.ok) {
            throw new Error(`HTTPエラー: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('📥 APIレスポンス:', data);
        
        // ★追加: 公開済み月リストを保存 (APIから受け取る)
        publishedMonths = data.published_months || [];
        
        const shiftsArray = data.shifts || [];
        
        // 負のuser_idを除外
        const validShifts = shiftsArray.filter(shift => parseInt(shift.user_id) > 0);
        
        if (validShifts.length === 0) {
            // データが0件の場合でも、カレンダー枠（今日を含む週）は表示したいので
            // 空のデータとして処理を続行させるためのダミー日付を入れる
            const today = formatDate(new Date());
            validShifts.push({ date: today, user_id: userId, dummy: true }); 
            // ※ dummyフラグをつけて後で除外
        }
        
        allGroupedShifts = groupShiftsByDate(validShifts);
        
        // ユニークな日付リスト作成（ダミー含む）
        const uniqueDates = Array.from(new Set(validShifts.map(s => s.date)));
        generateDatesByWeek(uniqueDates);
        
        if (datesByWeek.length === 0) {
            // それでも生成できなければエラー表示
            shiftContainer.innerHTML = '<p class="loading">表示できるシフトデータがありません。</p>';
            return;
        }
        
        displayCurrentWeekShifts();
        attachEventListeners();

    } catch (error) {
        console.error("❌ シフトデータの取得に失敗しました:", error);
        shiftContainer.innerHTML = `<p class="error">エラーが発生しました: ${error.message}</p>`;
        currentWeekRange.textContent = 'エラー';
        attachEventListeners();
    }
}

// === シフト表示ロジック ===

function displayCurrentWeekShifts() {
    if (datesByWeek.length === 0) return;

    const currentWeekDates = datesByWeek[currentWeekIndex];
    
    // 週の開始日と終了日計算
    const weekStartObj = getWeekStartDate(currentWeekDates[0]); 
    const weekEndObj = new Date(weekStartObj);
    weekEndObj.setDate(weekEndObj.getDate() + 6);

    const firstDateStr = formatDate(weekStartObj);
    const lastDateStr = formatDate(weekEndObj);

    currentWeekRange.textContent = `${formatDisplayDate(firstDateStr)} 〜 ${formatDisplayDate(lastDateStr)}`;

    const ul = document.createElement('ul');
    ul.className = 'shift-list';
    shiftContainer.innerHTML = '';

    // 月曜日から日曜日までの7日間をループ
    for (let i = 0; i < 7; i++) {
        const d = new Date(weekStartObj);
        d.setDate(d.getDate() + i);
        const dateStr = formatDate(d); // YYYY-MM-DD
        const monthStr = dateStr.substring(0, 7); // YYYY-MM

        // ヘッダー作成
        const dateHeader = document.createElement('div');
        dateHeader.className = 'shift-date-header';
        dateHeader.innerHTML = `<h3>📅 ${formatDisplayDate(dateStr)}</h3>`;
        ul.appendChild(dateHeader);

        // その日のシフトを取得
        const rawShifts = allGroupedShifts[dateStr] || [];
        // ダミーデータを除外
        const validShiftsOfDay = rawShifts.filter(s => !s.dummy && parseInt(s.user_id) > 0);

        if (validShiftsOfDay.length === 0) {
            // ★重要: シフトがない場合の表示判定
            // 条件: 「過去の日付」または「公開済みリストに含まれる月」なら "出勤者なし"
            // それ以外（未来の未公開月）なら "作成中"
            
            const todayStr = formatDate(new Date());
            const isPastOrToday = dateStr <= todayStr;
            const isPublished = publishedMonths.includes(monthStr);

            const li = document.createElement('li');
            li.className = 'shift-item';
            
            // 過去は公開設定に関係なく「なし」でOK。未来は公開設定を見る。
            if (isPastOrToday || isPublished) {
                li.innerHTML = `<p style="color: #888;">出勤者なし</p>`;
            } else {
                li.innerHTML = `<p style="color: #ff9800; font-weight:bold;">🚧 作成中</p>`;
            }
            ul.appendChild(li);

        } else {
            // シフトがある場合
            validShiftsOfDay.forEach(shift => {
                const li = document.createElement('li');
                li.className = 'shift-item';

                const isCurrentUser = String(shift.user_id) === String(userId);
                if (isCurrentUser) {
                    li.classList.add('current-user-shift');
                }
                
                const time_display = shift.start_time && shift.end_time ? 
                    `${shift.start_time} - ${shift.end_time}` : '時間未定';
                
                li.innerHTML = `
                    <p><strong>${shift.user_name}</strong>: ${time_display}${isCurrentUser ? ' (あなた)' : ''}</p>
                `;
                ul.appendChild(li);
            });
        }
    }

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
    // 重複登録防止のため、一度クローンして置換するテクニックを使用
    // (または addEventListener の前に removeEventListener する)
    
    prevWeekBtn.onclick = () => {
        if (currentWeekIndex > 0) {
            currentWeekIndex--;
            displayCurrentWeekShifts();
        }
    };

    nextWeekBtn.onclick = () => {
        if (currentWeekIndex < datesByWeek.length - 1) {
            currentWeekIndex++;
            displayCurrentWeekShifts();
        }
    };

    // ボトムナビゲーション
    const navItems = document.querySelectorAll('.nav-item');
    const currentPath = window.location.pathname;

    if (navItems.length > 0) {
        navItems.forEach(item => {
            const href = item.getAttribute('href');
            if (href && (href === currentPath || currentPath.startsWith(href))) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
            // タッチフィードバック
            item.addEventListener('click', function(e) {
                if (this.id === 'logout-link') return;
                this.style.transform = 'scale(0.95)';
                setTimeout(() => { this.style.transform = ''; }, 150);
            });
        });
    }
    
    // ログアウト処理
    const logoutLink = document.getElementById("logout-link");
    if (logoutLink) {
        // 重複防止のため onclick プロパティを使用
        logoutLink.onclick = function (e) {
            e.preventDefault(); 
            const logoutUrl = this.getAttribute('data-logout-url');
            if (confirm("ログアウトしますか？")) {
                window.location.href = logoutUrl;
            }
        };
    }
}

console.log('🎬 user_shift_view.js 読み込み完了');
fetchShifts();