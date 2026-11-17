/* TREBA CASH — преміум-шар: поле грошових іконок у hero, паралакс від курсора, прогрес читання.
 * Не чіпає футер і не підключається на рекламних лендингах. */
(function () {
  'use strict';
  var ICONS = {coin:'<circle cx="12" cy="12" r="9"/><path d="M9 10h6M9 13.2h6"/><path d="M14.6 8.2c-1.6-1.2-5-.7-5 1.5M9.4 15.8c1.6 1.2 5 .7 5-1.5"/>',wallet:'<rect x="3" y="6" width="18" height="13" rx="2.5"/><path d="M3 9.5h15.5a2.5 2.5 0 0 1 2.5 2.5"/><path d="M16 12.5h5v3.5h-5a1.75 1.75 0 0 1 0-3.5z"/>',card:'<rect x="2.5" y="5.5" width="19" height="13" rx="2.2"/><path d="M2.5 9.5h19M6 15h4"/>',stack:'<ellipse cx="12" cy="6" rx="7" ry="2.5"/><path d="M5 6v4c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V6M5 10v4c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-4M5 14v4c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-4"/>',note:'<rect x="2" y="7" width="20" height="10" rx="1.6"/><circle cx="12" cy="12" r="2.6"/><path d="M5.5 10v4M18.5 10v4"/>',percent:'<path d="M18.5 5.5l-13 13"/><circle cx="7" cy="7" r="2.3"/><circle cx="17" cy="17" r="2.3"/>',shield:'<path d="M12 3l7 3v5.2c0 4.4-3 7.9-7 9.8-4-1.9-7-5.4-7-9.8V6z"/><path d="M9 12l2.2 2.2L15.5 10"/>',chart:'<path d="M4 4v16h16"/><path d="M7.5 15l4-4.5 3 3L20 7"/><path d="M16 7h4v4"/>',calc:'<rect x="5" y="3" width="14" height="18" rx="2.2"/><path d="M8 7h8M8.5 11h.01M12 11h.01M15.5 11h.01M8.5 14.5h.01M12 14.5h.01M15.5 14.5h.01M8.5 18h.01M12 18h.01M15.5 18h.01"/>'};
  // x, y — % від hero; s — розмір px; d — глибина паралаксу; r — нахил; c — колір; o — непрозорість
  // Сторінки-статті: текст ліворуч, тож іконки — у правій третині й по краях
  var LAYOUT = [
    ['coin',    '80%', '12%', 64, 18, -12, 'g', .55],
    ['card',    '88%', '50%', 78, 10,  14, 'm', .35],
    ['wallet',  '76%', '66%', 54, 24,  -8, 'g', .40],
    ['stack',   '94%', '8%',  44, 30,   6, 'm', .30],
    ['note',    '86%', '86%', 62, 14, -16, 'm', .26],
    ['percent', '72%', '20%', 34, 34,  10, 'g', .32],
    ['chart',   '97%', '64%', 38, 20,  -6, 'm', .22],
    ['calc',    '70%', '90%', 30, 28,  12, 'g', .22],
    ['shield',  '64%', '4%',  28, 22,  -4, 'm', .20],
    ['coin',    '2%',  '88%', 26, 36,  20, 'g', .18]
  ];
  // Головна: праворуч світла картка калькулятора, тож іконки — між колонками, внизу ліворуч і по краях
  var LAYOUT_HOME = [
    ['coin',    '47%', '14%', 58, 18, -12, 'g', .50],
    ['card',    '44%', '70%', 70, 12,  14, 'm', .32],
    ['wallet',  '33%', '82%', 52, 24,  -8, 'g', .38],
    ['stack',   '95%', '6%',  44, 30,   6, 'm', .30],
    ['note',    '6%',  '88%', 56, 14, -16, 'm', .24],
    ['percent', '50%', '44%', 30, 34,  10, 'g', .30],
    ['chart',   '96%', '90%', 40, 20,  -6, 'm', .22],
    ['calc',    '2%',  '8%',  30, 28,  12, 'g', .20],
    ['shield',  '20%', '94%', 30, 22,  -4, 'm', .20]
  ];
  var COLORS = { g: '#e9b44c', m: '#9fe3bd' };
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function field(hero) {
    if (hero.querySelector('.tc-field')) return;
    var f = document.createElement('div');
    f.className = 'tc-field';
    f.setAttribute('aria-hidden', 'true');
    (hero.querySelector('.hero-right') ? LAYOUT_HOME : LAYOUT).forEach(function (l, i) {
      var el = document.createElement('span');
      el.className = 'tc-ico';
      el.style.cssText = '--x:' + l[1] + ';--y:' + l[2] + ';--s:' + l[3] + 'px;--d:' + l[4] / 10 + ';--r:' + l[5] + 'deg;--c:' +
        COLORS[l[6]] + ';--o:' + l[7] + ';--delay:' + (0.08 * i).toFixed(2) + 's;--t:' + (7 + (i % 5) * 1.6) + 's';
      el.innerHTML = '<svg viewBox="0 0 24 24">' + ICONS[l[0]] + '</svg>';
      f.appendChild(el);
    });
    hero.insertBefore(f, hero.firstChild);
    if (reduce || !window.matchMedia('(pointer: fine)').matches) return;
    var raf = 0;
    hero.addEventListener('pointermove', function (e) {
      var r = hero.getBoundingClientRect();
      var mx = ((e.clientX - r.left) / r.width - .5) * 2, my = ((e.clientY - r.top) / r.height - .5) * 2;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(function () { f.style.setProperty('--mx', mx.toFixed(3)); f.style.setProperty('--my', my.toFixed(3)); });
    });
    hero.addEventListener('pointerleave', function () { f.style.setProperty('--mx', 0); f.style.setProperty('--my', 0); });
  }

  function progress() {
    var art = document.querySelector('article.article');
    if (!art || document.querySelector('.tc-progress')) return;
    var bar = document.createElement('div');
    bar.className = 'tc-progress';
    bar.setAttribute('aria-hidden', 'true');
    document.body.appendChild(bar);
    var ticking = false;
    function upd() {
      var r = art.getBoundingClientRect(), h = r.height - window.innerHeight;
      var p = h > 0 ? Math.min(Math.max(-r.top / h, 0), 1) : 0;
      bar.style.setProperty('--p', p.toFixed(4)); ticking = false;
    }
    window.addEventListener('scroll', function () { if (!ticking) { ticking = true; requestAnimationFrame(upd); } }, { passive: true });
    upd();
  }

  function init() {
    var hero = document.querySelector('main .hero, section.hero, header.hero');
    if (hero) field(hero);
    progress();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
