// index.js (修正後の内容)

document.addEventListener("DOMContentLoaded", function() {
    
    // 🍔 メニュー開閉
    const hamburger = document.getElementById('hamburger');
    const menu = document.getElementById('menu');
    
    // 要素が存在することを確認してからリスナーを設定
    if (hamburger && menu) {
        hamburger.addEventListener('click', () => {
            hamburger.classList.toggle('active');
            menu.classList.toggle('active');
        });
    }

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
    // このイベントリスナーはDOMContentLoaded内にあるため、要素の存在を気にしなくて良い
    document.addEventListener("click", async (e) => {
        if (e.target.classList.contains("regen-btn")) {
            const btn = e.target;
            const question = btn.dataset.question;
            // メッセージ内容全体を更新するため、ここではclosest(".message")で親要素を取得
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
                
                // 新しいメッセージテキストと再生成ボタンを含むHTMLを作成
                // Flask側から新しいメッセージHTML全体を返してもらう方が確実だが、
                // JSONで答えだけが返る前提でDOMを更新
                const newText = data.answer;
                
                // botMessageのコンテンツを更新し、再生成ボタンを再配置
                const regenBtnHtml = `<button class="regen-btn" data-question="${question}">🔄再生成</button>`;
                botMessage.innerHTML = `${newText} ${regenBtnHtml}`;

            } catch {
                alert("再生成に失敗しました。");
                // 失敗した場合もボタンのテキストを元に戻す
                const originalText = btn.dataset.question; 
                botMessage.innerHTML = `${botMessage.childNodes[0].textContent} <button class="regen-btn" data-question="${originalText}">🔄再生成</button>`;
            } 
            // 注意: `finally`ブロックは、上記の`try`ブロックのDOM操作によってボタン要素自体が置き換えられてしまうため、ここでは使用せず、`try/catch`内で処理を完了させます。
        }
    });

});