// チャットボット JavaScript (既存機能 + ボトムナビゲーション対応版)

document.addEventListener("DOMContentLoaded", function() {
    
    // 💬 チャット送信処理（非同期送信）
    const chatForm = document.getElementById("chat-form");
    if (chatForm) {
        chatForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const input = document.getElementById("question");
            const userText = input.value.trim();
            if (!userText) return;

            const chatContainer = document.getElementById("chat-container");

            // ユーザーメッセージを追加
            const userMsg = document.createElement("div");
            userMsg.className = "message user";
            userMsg.textContent = userText;
            chatContainer.appendChild(userMsg);
            input.value = "";
            chatContainer.scrollTop = chatContainer.scrollHeight;

            // サーバーへ送信
            const response = await fetch("/chatbot/", {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: new URLSearchParams({ question: userText })
            });

            const html = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, "text/html");

            // 新しい履歴を取得して全体置き換え
            const newChat = doc.querySelector("#chat-container").innerHTML;
            chatContainer.innerHTML = newChat;
            chatContainer.scrollTop = chatContainer.scrollHeight;
        });
    }
    
    // 🗑 履歴削除ボタン
    const clearBtn = document.getElementById("clear-btn");
    if (clearBtn) {
        clearBtn.addEventListener("click", async () => {
            if (!confirm("チャット履歴を本当に消しますか？")) return;

            await fetch("/chatbot/clear", { method: "POST" });

            const chatContainer = document.getElementById("chat-container");
            chatContainer.innerHTML = '<div class="message bot">こんにちは！ご質問をどうぞ 😊</div>';
        });
    }

    // 🔄 再生成ボタン機能（イベント委譲を使用）
    document.addEventListener("click", async (e) => {
        if (e.target.classList.contains("regen-btn")) {
            const btn = e.target;
            const question = btn.dataset.question;
            const botMessage = btn.closest(".message"); 

            btn.disabled = true;
            btn.textContent = "再生成中...";

            try {
                const res = await fetch("/chatbot/regenerate", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: new URLSearchParams({ question })
                });

                const data = await res.json();
                const newText = data.answer;
                
                const regenBtnHtml = `<button class="regen-btn" data-question="${question}">🔄再生成</button>`;
                botMessage.innerHTML = `${newText} ${regenBtnHtml}`;

            } catch {
                alert("再生成に失敗しました。");
                const originalText = btn.dataset.question; 
                botMessage.innerHTML = `${botMessage.childNodes[0].textContent} <button class="regen-btn" data-question="${originalText}">🔄再生成</button>`;
            } 
        }
    });

    // === 📱 ボトムナビゲーション アクティブ状態管理 ===
    const navItems = document.querySelectorAll('.nav-item');
    const currentPath = window.location.pathname;

    if (navItems.length > 0) {
        // 現在のページに対応するナビアイテムをアクティブ化
        navItems.forEach(item => {
            const href = item.getAttribute('href');
            
            // パスが完全一致、または部分一致（サブページ対応）
            if (href && (href === currentPath || currentPath.startsWith(href))) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });

        // ナビアイテムクリック時のフィードバック
        navItems.forEach(item => {
            item.addEventListener('click', function(e) {
                // ログアウトリンクの場合は特別処理（下記で実装）
                if (this.id === 'logout-link') {
                    return;
                }
                
                // タップ時の視覚フィードバック
                this.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    this.style.transform = '';
                }, 150);
            });
        });
    }

    // === 🚪 ログアウト処理 ===
    const logoutLink = document.getElementById("logout-link");
    if (logoutLink) {
        logoutLink.addEventListener("click", function (e) {
            e.preventDefault(); 
            
            const logoutUrl = this.getAttribute('data-logout-url');
            
            if (!logoutUrl) {
                console.error("ログアウトURLが見つかりません。");
                return;
            }
            
            const confirmed = confirm("ログアウトしますか？");
            if (confirmed) {
                window.location.href = logoutUrl;
            }
        });
    }

    // Enterキーで送信（Shift+Enterで改行）
    const questionInput = document.getElementById('question');
    if (questionInput) {
        questionInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                chatForm.submit();
            }
        });
    }

    // 自動スクロール機能
    function scrollToBottom() {
        const chatContainer = document.getElementById('chat-container');
        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    }

    // ページ読み込み時に最下部へスクロール
    scrollToBottom();

    // メッセージが追加されたら自動スクロール（MutationObserver使用）
    const chatContainer = document.getElementById('chat-container');
    if (chatContainer) {
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.addedNodes.length > 0) {
                    scrollToBottom();
                }
            });
        });

        observer.observe(chatContainer, {
            childList: true,
            subtree: true
        });
    }
});