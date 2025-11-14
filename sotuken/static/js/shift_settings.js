const menuBtn = document.getElementById('menuBtn');
const sideMenu = document.getElementById('sideMenu');
const body = document.body;

menuBtn.addEventListener('click', () => {
    menuBtn.classList.toggle('active');
    sideMenu.classList.toggle('active');
    body.classList.toggle('menu-open');
});
