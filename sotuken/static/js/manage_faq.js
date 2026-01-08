// ハンバーガーメニューの制御
const menuIcon = document.getElementById('menuIcon');
const menuCloseBtn = document.getElementById('closeBtn'); // 名前を変更
const sideMenu = document.getElementById('sideMenu');
const overlay = document.getElementById('overlay');

if (menuIcon && menuCloseBtn && sideMenu && overlay) {
    // メニューを開く
    menuIcon.addEventListener('click', function() {
        console.log('メニューアイコンクリック'); // デバッグ用
        sideMenu.classList.add('active');
        overlay.classList.add('active');
    });

    // メニューを閉じる
    menuCloseBtn.addEventListener('click', function() {
        console.log('閉じるボタンクリック'); // デバッグ用
        sideMenu.classList.remove('active');
        overlay.classList.remove('active');
    });

    // オーバーレイをクリックで閉じる
    overlay.addEventListener('click', function() {
        sideMenu.classList.remove('active');
        overlay.classList.remove('active');
    });
}

// ログアウト機能（現在のHTMLには存在しないが、念のため残す）
const logoutLink = document.getElementById("logout-link");

if (logoutLink) {
  const logoutUrl = logoutLink.getAttribute('data-logout-url');
  
  logoutLink.addEventListener("click", function (e) {
    e.preventDefault(); 
    const confirmed = confirm("ログアウトしますか？");
    if (confirmed && logoutUrl) {
      window.location.href = logoutUrl;
    }
  });
}