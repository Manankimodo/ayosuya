// ==========================================
// グローバル関数（HTMLから直接呼ばれる）
// ==========================================

// タブ切り替え関数
function switchTab(type) {
    // エリアの表示・非表示
    const weekdayArea = document.getElementById('area-weekday');
    const holidayArea = document.getElementById('area-holiday');
    
    if (weekdayArea && holidayArea) {
        weekdayArea.style.display = (type === 'weekday') ? 'block' : 'none';
        holidayArea.style.display = (type === 'holiday') ? 'block' : 'none';
    }

    // 説明文の切り替え
    const descWeekday = document.getElementById('desc-weekday');
    const descHoliday = document.getElementById('desc-holiday');
    
    if (descWeekday && descHoliday) {
        descWeekday.style.display = (type === 'weekday') ? 'inline' : 'none';
        descHoliday.style.display = (type === 'holiday') ? 'inline' : 'none';
    }

    // ボタンのアクティブ状態切り替え
    const btnW = document.getElementById('btn-weekday');
    const btnH = document.getElementById('btn-holiday');
    
    if (btnW && btnH) {
        if (type === 'weekday') {
            btnW.classList.add('active');
            btnH.classList.remove('active');
        } else {
            btnH.classList.add('active');
            btnW.classList.remove('active');
        }
    }

    // タブの状態を保存
    sessionStorage.setItem('activeTab', type);
}

// テーマ切り替え関数
function toggleTheme() {
    const body = document.body;
    const btn = document.getElementById('themeBtn');
    
    // クラスを付け外し
    body.classList.toggle('light-mode');
    
    // 現在の状態を確認
    const isLight = body.classList.contains('light-mode');
    
    // ボタンの文字を変える
    if (btn) {
        btn.textContent = isLight ? "🌙 ダークモードへ" : "☀️ ライトモードへ";
    }
    
    // 設定をブラウザに保存（次回アクセス用）
    localStorage.setItem('theme', isLight ? 'light' : 'dark');
}

// ==========================================
// DOMContentLoaded - ページ読み込み時の処理
// ==========================================
document.addEventListener("DOMContentLoaded", function() {
    
    console.log("✅ ページ読み込み完了");
    
    // ==========================================
    // 1. ハンバーガーメニューの処理
    // ==========================================
    const menuBtn = document.getElementById('menuBtn');
    const sideMenu = document.getElementById('sideMenu');
    const closeBtn = document.getElementById('closeBtn');

    if (menuBtn && sideMenu) {
        // メニューを開く
        menuBtn.addEventListener('click', function() {
            sideMenu.classList.toggle('active');
            console.log("🍔 メニュー開閉");
        });
        
        // 閉じるボタン
        if (closeBtn) {
            closeBtn.addEventListener('click', function() {
                sideMenu.classList.remove('active');
                console.log("❌ メニュー閉じる");
            });
        }
        
        console.log("✅ ハンバーガーメニューを初期化しました");
    } else {
        console.error("❌ メニュー要素が見つかりません (ID: menuBtn, sideMenu)");
    }

    // ==========================================
    // 2. テーマ復元
    // ==========================================
    const savedTheme = localStorage.getItem('theme');
    const themeBtn = document.getElementById('themeBtn');
    
    if (savedTheme === 'light') {
        document.body.classList.add('light-mode');
        if (themeBtn) themeBtn.textContent = "🌙 ダークモードへ";
        console.log("🌞 ライトモードで起動");
    } else {
        console.log("🌙 ダークモードで起動");
    }

    // ==========================================
    // 3. タブ状態の復元
    // ==========================================
    const savedTab = sessionStorage.getItem('activeTab');
    if (savedTab) {
        switchTab(savedTab);
        console.log(`✅ タブ復元: ${savedTab}`);
    }

    // ==========================================
    // 4. 特別時間フォームの処理 (保存機能)
    // ==========================================
    const specialHoursForm = document.getElementById('special-hours-add-form') || 
                             document.querySelector('form[action*="add_special_hours"]');
    
    if (specialHoursForm) {
        console.log('✅ 特別時間フォームを初期化しました');

        // 送信イベント
        specialHoursForm.addEventListener('submit', async function(e) {
            e.preventDefault(); // リロード阻止
            e.stopPropagation();

            const formData = new FormData(this);
            const data = {
                date: formData.get('date'),
                start_time: formData.get('start_time'),
                end_time: formData.get('end_time'),
                reason: formData.get('reason') || ''
            };

            console.log('📤 特別時間を送信:', data);

            try {
                const response = await fetch(this.action, {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify(data)
                });

                if (response.ok) {
                    const result = await response.json();
                    console.log('✅ 保存成功:', result);
                    
                    // テーブル更新処理
                    const tbody = document.querySelector('#special-hours-table tbody');
                    if (tbody) {
                        const emptyRow = tbody.querySelector('td[colspan="5"]');
                        if (emptyRow) emptyRow.parentElement.remove();

                        const newRow = document.createElement('tr');
                        newRow.style.borderBottom = '1px solid #eee';
                        const deleteAction = this.action.replace('add', 'delete');
                        
                        newRow.innerHTML = `
                            <td style="padding:10px;">${data.date}</td>
                            <td style="padding:10px;">${data.start_time}</td>
                            <td style="padding:10px;">${data.end_time}</td>
                            <td style="padding:10px;">${data.reason}</td>
                            <td style="padding:10px; text-align:center;">
                                <form class="delete-special-hours-form" action="${deleteAction}" method="POST" style="display:inline;">
                                    <input type="hidden" name="date" value="${data.date}">
                                    <button type="submit" style="background:#ff5252; color:white; border:none; padding:5px 10px; border-radius:3px; cursor:pointer;">削除</button>
                                </form>
                            </td>
                        `;
                        tbody.appendChild(newRow);
                        attachDeleteListener(newRow.querySelector('.delete-special-hours-form'));
                    }

                    this.reset();
                    showSuccessMessage(this, '✓ 追加しました');

                } else {
                    console.error('❌ サーバーエラー:', response.status);
                    alert('エラーが発生しました');
                }
            } catch (error) {
                console.error('❌ 通信エラー:', error);
                alert('通信エラーが発生しました');
            }
        });
    }

    // ==========================================
    // 5. 削除機能
    // ==========================================
    function attachDeleteListener(form) {
        if (!form) return;
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            if (!confirm('削除しますか？')) return;

            const formData = new FormData(this);
            const data = { date: formData.get('date') };

            console.log('🗑️ 削除リクエスト:', data);

            try {
                const response = await fetch(this.action, {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify(data)
                });

                if (response.ok) {
                    console.log('✅ 削除成功');
                    const row = this.closest('tr');
                    row.remove();
                    const tbody = document.querySelector('#special-hours-table tbody');
                    if (tbody && tbody.children.length === 0) {
                        const emptyRow = document.createElement('tr');
                        emptyRow.innerHTML = '<td colspan="5" style="text-align:center; padding:20px; color:#aaa;">特別設定なし</td>';
                        tbody.appendChild(emptyRow);
                    }
                } else {
                    console.error('❌ 削除失敗:', response.status);
                    alert('削除に失敗しました');
                }
            } catch (error) {
                console.error('❌ エラー:', error);
                alert('通信エラーが発生しました');
            }
        });
    }

    // 既存の削除ボタンに適用
    document.querySelectorAll('.delete-special-hours-form').forEach(form => {
        attachDeleteListener(form);
    });

    // 成功メッセージ表示
    function showSuccessMessage(form, message) {
        let msgEl = form.querySelector('.success-message');
        if (!msgEl) {
            msgEl = document.createElement('span');
            msgEl.className = 'success-message';
            msgEl.style.cssText = 'margin-left:10px; color:#4caf50; font-weight:bold;';
            form.appendChild(msgEl);
        }
        msgEl.textContent = message;
        msgEl.style.display = 'inline';
        setTimeout(() => { msgEl.style.display = 'none'; }, 2000);
    }

    console.log("✅ すべての機能を初期化完了");
});