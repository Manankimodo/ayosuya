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
    const menuBtn = document.getElementById('menuBtn');
    const sideMenu = document.getElementById('sideMenu');

    // 1. ハンバーガーメニューの開閉機能
    if (menuBtn && sideMenu) {
        menuBtn.addEventListener('click', function() {
            // ボタンとメニューの両方に 'active' クラスを切り替え
            menuBtn.classList.toggle('active');
            sideMenu.classList.toggle('active');
        });
    }

    // 2. メニュー外をクリックで閉じる機能
    document.addEventListener('click', function(e) {
        // メニューが開いていて、クリックした要素がボタンでもメニュー内でもない場合
        if (sideMenu && sideMenu.classList.contains('active') && 
            !sideMenu.contains(e.target) && 
            !menuBtn.contains(e.target)) {
            
            menuBtn.classList.remove('active');
            sideMenu.classList.remove('active');
        }
    });
});
