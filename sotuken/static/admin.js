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
