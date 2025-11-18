document.addEventListener('DOMContentLoaded', function() {
    // HTMLからメニュー要素を取得
    const menuBtn = document.getElementById('menuBtn');
    const sideMenu = document.getElementById('sideMenu');

    // メニューの開閉機能
    if (menuBtn && sideMenu) {
        menuBtn.addEventListener('click', function() {
            // ボタンとメニューの両方に 'active' クラスを切り替え
            menuBtn.classList.toggle('active');
            sideMenu.classList.toggle('active');
        });
    }

    // メニュー外をクリックで閉じる機能
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