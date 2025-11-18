document.addEventListener('DOMContentLoaded', function() {
    const hamburger = document.getElementById('hamburger');
    const menu = document.getElementById('menu');
    const logoutLink = document.getElementById('logout-link');

    // 1. ハンバーガーメニューの開閉機能
    if (hamburger && menu) {
        hamburger.addEventListener('click', function() {
            // ハンバーガーアイコンのアニメーション切り替え
            hamburger.classList.toggle('active');
            // メニューの表示/非表示を切り替え
            menu.classList.toggle('open');
        });
    }

    // // 2. ログアウト確認機能
    // if (logoutLink) {
    //     logoutLink.addEventListener('click', function(e) {
    //         e.preventDefault(); // リンクのデフォルト動作を停止

    //         // 確認ダイアログを表示
    //         if (confirm('ログアウトしますか？')) {
    //             // 「OK」が押された場合、data-logout-urlからURLを取得して遷移
    //             const logoutUrl = this.getAttribute('data-logout-url');
    //             if (logoutUrl) {
    //                 window.location.href = logoutUrl;
    //             }
    //         }
    //         // 「キャンセル」が押された場合、何もしない
    //     });
    // }

    // 3. メニュー外をクリックで閉じる機能 (任意)
    document.addEventListener('click', function(e) {
        // メニューが開いていて、クリックした要素がハンバーガーでもメニュー内でもない場合
        if (menu.classList.contains('open') && 
            !menu.contains(e.target) && 
            !hamburger.contains(e.target)) {
            
            hamburger.classList.remove('active');
            menu.classList.remove('open');
        }
    });
});