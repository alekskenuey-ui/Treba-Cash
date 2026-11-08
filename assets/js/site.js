/* TREBA CASH — спільна поведінка хедера: мобільне меню, тінь при скролі, активний пункт. */
(function () {
  'use strict';
  var header = document.getElementById('main-header');
  var burger = document.getElementById('hamburger');
  var mobile = document.getElementById('mobile-nav');

  function setOpen(open) {
    if (!mobile) return;
    mobile.classList.toggle('open', open);
    if (burger) burger.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  // capture-фаза + stopImmediatePropagation: старі inline/сторінкові обробники
  // не відпрацюють вдруге (інакше меню відкриється й одразу закриється).
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('#hamburger');
    if (b) { e.stopImmediatePropagation(); e.preventDefault(); setOpen(!mobile.classList.contains('open')); return; }
    if (mobile && mobile.classList.contains('open') && !e.target.closest('#mobile-nav')) setOpen(false);
  }, true);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') setOpen(false); });

  function onScroll() { if (header) header.classList.toggle('scrolled', window.scrollY > 10); }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  // Активний пункт меню: точний збіг або розділ (/blog/..., /propozytsiyi/...)
  var path = location.pathname.replace(/index\.html$/, '');
  document.querySelectorAll('.nav a, .mobile-nav a').forEach(function (a) {
    var href = a.getAttribute('href');
    if (!href || href.charAt(0) !== '/') return;
    var on = href === '/' ? path === '/' : path.indexOf(href) === 0;
    if (on) a.setAttribute('aria-current', 'page');
  });
})();
