// 🍔 メニュー開閉
document.getElementById('hamburger').addEventListener('click', () => {
    document.getElementById('hamburger').classList.toggle('active');
    document.getElementById('menu').classList.toggle('active');
});

// 💬 チャット送信処理（非同期送信）
document.getElementById("chat-form").addEventListener("submit", async (e) => {
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

// 🗑 履歴削除ボタン
document.getElementById("clear-btn").addEventListener("click", async () => {
    if (!confirm("チャット履歴を本当に消しますか？")) return;

    await fetch("/chatbot/clear", { method: "POST" });

    const chatContainer = document.getElementById("chat-container");
    chatContainer.innerHTML = '<div class="message bot">こんにちは！ご質問をどうぞ 😊</div>';
});

// 🔄 再生成ボタン機能（Ajax）
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
            botMessage.childNodes[0].textContent = data.answer;
        } catch {
            alert("再生成に失敗しました。");
        } finally {
            btn.disabled = false;
            btn.textContent = "🔄再生成";
        }
    }
});
