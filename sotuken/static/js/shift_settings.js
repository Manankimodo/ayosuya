
document.addEventListener("DOMContentLoaded", function() {
    
    // ==========================================
    // 1. ハンバーガーメニューの処理 (修正済み)
    // ==========================================
    // あなたのHTMLのID (menuBtn, sideMenu) に合わせました
    const menuBtn = document.getElementById('menuBtn');
    const sideMenu = document.getElementById('sideMenu');

    if (menuBtn && sideMenu) {
        menuBtn.addEventListener('click', function() {
            sideMenu.classList.toggle('active');
        });
        console.log("✅ ハンバーガーメニューを初期化しました");
    } else {
        console.error("❌ メニュー要素が見つかりません (ID: menuBtn, sideMenu)");
    }

    // ==========================================
    // 2. タブ切り替え処理 (平日/休日)
    // ==========================================
    // もしタブ機能があるなら、ここも動くようにしておきます
    const tabBtns = document.querySelectorAll('.tab-btn');
    const weekdayArea = document.getElementById('area-weekday');
    const holidayArea = document.getElementById('area-holiday');

    if (tabBtns.length > 0 && weekdayArea && holidayArea) {
        tabBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                // すべてのタブからactiveを外す
                tabBtns.forEach(b => b.classList.remove('active'));
                // クリックされたタブにactiveをつける
                this.classList.add('active');

                const type = this.getAttribute('data-type') || (this.textContent.includes('土日') ? 'holiday' : 'weekday');

                if (type === 'weekday') {
                    weekdayArea.style.display = 'block';
                    holidayArea.style.display = 'none';
                    this.style.background = '#3f51b5'; // 青
                    this.style.color = 'white';
                    // もう片方のボタンの色を戻す
                    tabBtns.forEach(b => {
                        if(b !== this) { b.style.background = '#e0e0e0'; b.style.color = '#666'; }
                    });
                } else {
                    weekdayArea.style.display = 'none';
                    holidayArea.style.display = 'block';
                    this.style.background = '#f44336'; // 赤
                    this.style.color = 'white';
                    // もう片方のボタンの色を戻す
                    tabBtns.forEach(b => {
                        if(b !== this) { b.style.background = '#e0e0e0'; b.style.color = '#666'; }
                    });
                }
            });
        });
    }

    // ==========================================
    // 3. 特別時間フォームの処理 (保存機能)
    // ==========================================
    const specialHoursForm = document.getElementById('special-hours-add-form') || 
                             document.querySelector('form[action*="add_special_hours"]');
    
    if (specialHoursForm) {
        // イベントリスナー重複防止のためクローン
        const newForm = specialHoursForm.cloneNode(true);
        specialHoursForm.parentNode.replaceChild(newForm, specialHoursForm);
        
        console.log('✅ 特別時間フォームを初期化しました');

        // 送信イベント
        newForm.addEventListener('submit', async function(e) {
            e.preventDefault(); // リロード阻止
            e.stopPropagation();

            const formData = new FormData(this);
            const data = {
                date: formData.get('date'),
                start_time: formData.get('start_time'),
                end_time: formData.get('end_time'),
                reason: formData.get('reason') || ''
            };

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
                    alert('エラーが発生しました');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('通信エラーが発生しました');
            }
        });
    }

    // ==========================================
    // 4. 削除機能
    // ==========================================
    function attachDeleteListener(form) {
        if(!form) return;
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            if (!confirm('削除しますか？')) return;

            const formData = new FormData(this);
            const data = { date: formData.get('date') };

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
                    const row = this.closest('tr');
                    row.remove();
                    const tbody = document.querySelector('#special-hours-table tbody');
                    if (tbody && tbody.children.length === 0) {
                        const emptyRow = document.createElement('tr');
                        emptyRow.innerHTML = '<td colspan="5" style="text-align:center; padding:20px; color:#aaa;">特別設定なし</td>';
                        tbody.appendChild(emptyRow);
                    }
                } else {
                    alert('削除に失敗しました');
                }
            } catch (error) {
                console.error('Error:', error);
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
});