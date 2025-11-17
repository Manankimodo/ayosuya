document.addEventListener('DOMContentLoaded', function() {
    const hamburger = document.getElementById('hamburger');
    const menu = document.getElementById('menu');

    // 1. ハンバーガーメニューの開閉機能
    if (hamburger && menu) {
        hamburger.addEventListener('click', function() {
            // ハンバーガーアイコンのアニメーション切り替え
            hamburger.classList.toggle('active');
            // メニューの表示/非表示を切り替え (left: -250px <-> left: 0)
            menu.classList.toggle('open');
        });
    }

    // 2. メニュー外をクリックで閉じる機能
    document.addEventListener('click', function(e) {
        // メニューが開いていて、クリックした要素がハンバーガーでもメニュー内でもない場合
        if (menu && menu.classList.contains('open') && 
            !menu.contains(e.target) && 
            !hamburger.contains(e.target)) {
            
            hamburger.classList.remove('active');
            menu.classList.remove('open');
        }
    });
});