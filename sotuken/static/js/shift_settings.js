// ==========================================
<<<<<<< HEAD
// グローバル関数（HTMLから直接呼ばれる）
=======
// グローバル関数(HTMLから直接呼ばれる)
>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
// ==========================================

// タブ切り替え関数
function switchTab(type) {
    // エリアの表示・非表示
    const weekdayArea = document.getElementById('area-weekday');
    const holidayArea = document.getElementById('area-holiday');
<<<<<<< HEAD
    
=======

>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
    if (weekdayArea && holidayArea) {
        weekdayArea.style.display = (type === 'weekday') ? 'block' : 'none';
        holidayArea.style.display = (type === 'holiday') ? 'block' : 'none';
    }

    // 説明文の切り替え
    const descWeekday = document.getElementById('desc-weekday');
    const descHoliday = document.getElementById('desc-holiday');
<<<<<<< HEAD
    
=======

>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
    if (descWeekday && descHoliday) {
        descWeekday.style.display = (type === 'weekday') ? 'inline' : 'none';
        descHoliday.style.display = (type === 'holiday') ? 'inline' : 'none';
    }

    // ボタンのアクティブ状態切り替え
    const btnW = document.getElementById('btn-weekday');
    const btnH = document.getElementById('btn-holiday');
<<<<<<< HEAD
    
=======

>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
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
<<<<<<< HEAD
    
    // クラスを付け外し
    body.classList.toggle('light-mode');
    
    // 現在の状態を確認
    const isLight = body.classList.contains('light-mode');
    
=======

    // クラスを付け外し
    body.classList.toggle('light-mode');

    // 現在の状態を確認
    const isLight = body.classList.contains('light-mode');

>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
    // ボタンの文字を変える
    if (btn) {
        btn.textContent = isLight ? "🌙 ダークモードへ" : "☀️ ライトモードへ";
    }
<<<<<<< HEAD
    
    // 設定をブラウザに保存（次回アクセス用）
=======

    // 設定をブラウザに保存(次回アクセス用)
>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
    localStorage.setItem('theme', isLight ? 'light' : 'dark');
}

// ==========================================
// DOMContentLoaded - ページ読み込み時の処理
// ==========================================
document.addEventListener("DOMContentLoaded", function() {
<<<<<<< HEAD
    
    console.log("✅ ページ読み込み完了");
    
=======
    console.log("✅ ページ読み込み完了");

>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
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
<<<<<<< HEAD
        
=======

>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
        // 閉じるボタン
        if (closeBtn) {
            closeBtn.addEventListener('click', function() {
                sideMenu.classList.remove('active');
                console.log("❌ メニュー閉じる");
            });
        }
<<<<<<< HEAD
        
=======

>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
        console.log("✅ ハンバーガーメニューを初期化しました");
    } else {
        console.error("❌ メニュー要素が見つかりません (ID: menuBtn, sideMenu)");
    }

    // ==========================================
    // 2. テーマ復元
    // ==========================================
    const savedTheme = localStorage.getItem('theme');
    const themeBtn = document.getElementById('themeBtn');
<<<<<<< HEAD
    
=======

>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
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
<<<<<<< HEAD
    const specialHoursForm = document.getElementById('special-hours-add-form') || 
                             document.querySelector('form[action*="add_special_hours"]');
    
=======
    const specialHoursForm = document.getElementById('special-hours-add-form') ||
                            document.querySelector('form[action*="add_special_hours"]');

>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
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
<<<<<<< HEAD
                    headers: { 
=======
                    headers: {
>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify(data)
                });

                if (response.ok) {
                    const result = await response.json();
                    console.log('✅ 保存成功:', result);
<<<<<<< HEAD
                    
=======

>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
                    // テーブル更新処理
                    const tbody = document.querySelector('#special-hours-table tbody');
                    if (tbody) {
                        const emptyRow = tbody.querySelector('td[colspan="5"]');
                        if (emptyRow) emptyRow.parentElement.remove();

                        const newRow = document.createElement('tr');
                        newRow.style.borderBottom = '1px solid #eee';
                        const deleteAction = this.action.replace('add', 'delete');
<<<<<<< HEAD
                        
=======

>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
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
<<<<<<< HEAD
            if (!confirm('削除しますか？')) return;
=======
            if (!confirm('削除しますか?')) return;
>>>>>>> 829944afb48f375272349e902fcb145bc303bc84

            const formData = new FormData(this);
            const data = { date: formData.get('date') };

            console.log('🗑️ 削除リクエスト:', data);

            try {
                const response = await fetch(this.action, {
                    method: 'POST',
<<<<<<< HEAD
                    headers: { 
=======
                    headers: {
>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
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

// ==========================================
<<<<<<< HEAD
// 6. 人数上限のバリデーション処理（イベント委譲版）
=======
// 6. 人数上限のバリデーション処理(イベント委譲版)
>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
// ==========================================

// ページ内のどこかに入力があったらすべてキャッチする
document.addEventListener('input', function(e) {
    // ターゲットが「必要人数(required_count)」だった場合のみ動く
    if (e.target && e.target.name === 'required_count') {
        const input = e.target;
        const maxPeopleInput = document.querySelector('input[name="max_people_per_shift"]');
<<<<<<< HEAD
        
=======

>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
        if (!maxPeopleInput) return;

        const currentMax = parseInt(maxPeopleInput.value) || 0;
        const val = parseInt(input.value) || 0;

<<<<<<< HEAD
        // 警告メッセージ用の要素を取得（なければ作る）
=======
        // 警告メッセージ用の要素を取得(なければ作る)
>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
        let errorMsg = input.parentNode.querySelector('.limit-warning');
        if (!errorMsg) {
            errorMsg = document.createElement('div');
            errorMsg.className = 'limit-warning';
            errorMsg.style.cssText = 'color: #d32f2f; font-size: 11px; font-weight: bold; margin-top: 4px;';
            input.parentNode.appendChild(errorMsg);
        }

        // 上限チェック
        if (val > currentMax) {
            input.value = currentMax; // 数字を上限に戻す
<<<<<<< HEAD
            
            // 警告の見た目（赤くする）
=======

            // 警告の見た目(赤くする)
>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
            input.style.border = "2px solid #d32f2f";
            input.style.backgroundColor = "#ffebee";
            errorMsg.textContent = `⚠️ 最大${currentMax}名までです`;

            // 1.2秒後に元に戻す
            setTimeout(() => {
                input.style.border = "";
                input.style.backgroundColor = "";
                errorMsg.textContent = "";
            }, 1200);
        } else {
            // 正常範囲内なら警告を消す
            errorMsg.textContent = "";
            input.style.border = "";
            input.style.backgroundColor = "";
        }
    }
});

<<<<<<< HEAD
console.log("🚀 バリデーション監視システムが起動しました");

/**
 * 1. ページの状態（スクロール位置・タブ）の保存と復元
 */
window.addEventListener('beforeunload', () => {
    // 現在のスクロール位置を保存
    sessionStorage.setItem('scrollPosition', window.scrollY);
    
    // 現在アクティブなタブを保存（要素が存在する場合のみ）
    const holidayBtn = document.getElementById('btn-holiday');
    if (holidayBtn) {
        const activeTab = holidayBtn.classList.contains('active') ? 'holiday' : 'weekday';
        sessionStorage.setItem('activeTab', activeTab);
    }
});

document.addEventListener('DOMContentLoaded', () => {
    // タブの復元
    const savedTab = sessionStorage.getItem('activeTab');
    if (savedTab && typeof window.switchTab === 'function') {
        window.switchTab(savedTab); 
    }

    // スクロール位置の復元
    const scrollPosition = sessionStorage.getItem('scrollPosition');
    if (scrollPosition) {
        setTimeout(() => {
            window.scrollTo(0, parseInt(scrollPosition));
            sessionStorage.removeItem('scrollPosition');
        }, 10);
    }
});

/**
 * 2. 需要リセット処理（平日/土日祝 別）
 */
async function handleResetDemand(event, dayType) {
    event.preventDefault(); 
    event.stopPropagation(); // ★追加：イベント伝播を停止

    const confirmMsg = dayType === 'weekday' ? '平日の設定を全て削除しますか？' : '土日祝の設定を全て削除しますか？';
    if (!confirm(confirmMsg)) return;

    const form = event.target;
    const url = form.action;

    try {
        // ★修正：FormDataをそのまま送信
        const response = await fetch(url, {
            method: 'POST',
            body: new FormData(form) // Content-Typeヘッダーを自動設定
        });

        if (response.ok) {
            const result = await response.json();
            
            if (result.success) {
                // 画面更新処理
                const tableSection = form.closest('div[style*="background"]'); // より具体的なセレクタ
                const tbody = tableSection ? tableSection.querySelector('tbody') : null;
                if (tbody) {
                    const emptyMsg = dayType === 'weekday' ? '平日' : '土日祝';
                    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:#aaa;">${emptyMsg}の設定がありません</td></tr>`;
                }
                
                const title = tableSection ? tableSection.querySelector('h4') : null;
                if (title) {
                    title.textContent = title.textContent.replace(/\(\d+ 件\)/, '(0 件)');
                }
                
                alert(result.message || 'リセットしました'); // ★ユーザーへのフィードバック追加
                console.log(`✅ ${dayType} reset successful`);
            } else {
                alert('エラー: ' + (result.message || 'リセットに失敗しました。'));
            }
        } else {
            const errorText = await response.text();
            console.error('Server error:', errorText);
            alert('サーバー通信エラーが発生しました。');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('通信エラーが発生しました: ' + error.message);
    }
}

/**
 * 3. 全ての設定リセット（修正版）
 */
async function handleResetAll(event) {
    event.preventDefault();
    event.stopPropagation(); // ★追加

    if (!confirm('平日・土日祝の全ての設定を削除してリセットしますか？')) return;

    const form = event.target;
    const url = form.action;

    try {
        // ★修正：FormDataをそのまま送信（他の関数と統一）
        const response = await fetch(url, {
            method: 'POST',
            body: new FormData(form) // Content-Typeを自動設定
        });

        if (response.ok) {
            const result = await response.json();

            if (result.success) {
                // 画面内の全ての需要リストをリセット表示にする
                const sections = document.querySelectorAll('.demand-list > div[style*="background"]');
                sections.forEach(section => {
                    const h4 = section.querySelector('h4');
                    const tbody = section.querySelector('tbody');
                    if (tbody && h4) {
                        const typeName = h4.textContent.includes('平日') ? '平日' : '土日祝';
                        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:#aaa;">${typeName}の設定がありません</td></tr>`;
                        h4.textContent = h4.textContent.replace(/\(\d+ 件\)/, '(0 件)');
                    }
                });
                
                alert(result.message || '全てリセットしました'); // ★フィードバック追加
                console.log('✅ All demands reset successful');
            } else {
                alert('エラー: ' + (result.message || '全てのリセットに失敗しました。'));
            }
        } else {
            const errorText = await response.text();
            console.error('Server error:', errorText);
            alert('サーバー通信エラーが発生しました。');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('通信エラーが発生しました: ' + error.message);
    }
}
=======
console.log("🚀 バリデーション監視システムが起動しました");
>>>>>>> 829944afb48f375272349e902fcb145bc303bc84
