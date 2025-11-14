// shift_settings.js

document.addEventListener('DOMContentLoaded', function() {
    const menuBtn = document.getElementById('menuBtn');
    const sideMenu = document.getElementById('sideMenu');
    const body = document.body;
    
    // 要素が存在するか確認してからイベントリスナーを登録
    if (menuBtn && sideMenu) {
        menuBtn.addEventListener('click', () => {
            menuBtn.classList.toggle('active');
            sideMenu.classList.toggle('active');
            body.classList.toggle('menu-open');
        });
    } else {
        console.error('ハンバーガーメニューに必要な要素が見つかりません。');
    }
});
