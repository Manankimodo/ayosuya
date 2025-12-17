document.addEventListener('DOMContentLoaded', function() {
  console.log("✅ admin.js loaded"); // ← これ追加
  const btn = document.getElementById('make-shift-btn');
  if (!btn) {
    console.error("❌ make-shift-btn が見つかりません！");
    return;
  }

  btn.addEventListener('click', async () => {
    console.log("🖱️ シフト自動作成ボタンが押されました"); // ← これ追加
    const res = await fetch('/makeshift/generate', { method: 'POST' });
    const data = await res.json();
    console.log("📡 fetch result:", data); // ← これ追加

    if (data.status === 'ok') {
      alert('✅ シフトを作成しました！');
      if (data.redirect) {
        window.location.href = data.redirect;
      }
    } else {
      alert('❌ シフト作成に失敗しました。');
    }
  });
});

document.addEventListener('DOMContentLoaded', function() {
    const menuIcon = document.getElementById('menuIcon');
    const sideMenu = document.getElementById('sideMenu');
    const closeBtn = document.getElementById('closeBtn');

    // 1. ハンバーガーメニューを開く
    if (menuIcon && sideMenu) {
        menuIcon.addEventListener('click', function() {
            sideMenu.classList.add('active');
        });
    }

    // 2. 閉じるボタンでメニューを閉じる
    if (closeBtn && sideMenu) {
        closeBtn.addEventListener('click', function() {
            sideMenu.classList.remove('active');
        });
    }

    // 3. メニュー内のリンクをクリックしたら閉じる
    if (sideMenu) {
        sideMenu.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', function() {
                sideMenu.classList.remove('active');
            });
        });
    }
});