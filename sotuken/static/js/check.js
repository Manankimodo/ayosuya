// アラートを表示して遷移を分岐
const result = confirm("あなたは管理者ですか？");
if (result) {
    // はい → 管理者パスワード入力
    const adminPass = prompt("管理者パスワードを入力してください：");
    if (adminPass === "1") {
        window.location.href = "/login/admin";  // ✅ Blueprint対応
    } else {
        alert("パスワードが違います。ログイン画面に戻ります。");
        window.location.href = "/login/shift";  // ✅ Blueprint対応
    }
} else {
    // いいえ → シフト確認画面へ
    window.location.href = "/calendar";  // ✅ Blueprint対応
}
