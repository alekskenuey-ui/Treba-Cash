/* TREBA CASH — вітрина у статтях «Пропозицій» і «Рейтингів».
 * 1) Компактні картки: номер #01, назва МФО під логотипом, 3D-кнопка, позначка «Заявку подано».
 * 2) Механіка «Подайте заявку в 2–3 МФО»: блок над сіткою + липка панель «Шанс N/3».
 * 3) Нижня панель «ТОП-3 пропозиції сьогодні» (Minibank, FreshCash, Finstep.Space) з даними з фіду.
 * Сітку малює сама сторінка (#offers-grid); цей скрипт лише доповнює картки, коли вони з'являються.
 * Вибрані МФО зберігаються в sessionStorage (спільно з /porivnyannya-mfo/). */
(function () {
  'use strict';
  var grid = document.getElementById('offers-grid');
  if (!grid) return;

  var APPLY_KEY = 'tcAppliedMfo';
  var DOCK_KEY = 'tcTop3DockClosed';
  var GOAL = 3;
  var DOCK_MFO = ['Minibank', 'FreshCash', 'Finstep.Space'];
  var DOCK_LABELS = ['👑 #1 Лідер', '#2 Онлайн', '#3 Онлайн'];
  var TEXTS = [
    'Подайте заявку в 2–3 МФО — так більше шансів на схвалення',
    'Чудово! Додайте ще 1–2 МФО для вищого шансу',
    'Ще одна заявка — і шанс найвищий',
    '✓ Готово! Очікуйте рішення від МФО'
  ];

  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;'); }
  function fmt(n) { return new Intl.NumberFormat('uk-UA').format(Math.round(n)); }
  function ss(k, v) {
    try { if (v === undefined) return sessionStorage.getItem(k); sessionStorage.setItem(k, v); } catch (e) { return null; }
  }
  function getApplied() {
    try { var v = JSON.parse(ss(APPLY_KEY) || '[]'); return Array.isArray(v) ? v : []; } catch (e) { return []; }
  }
  function addApplied(name) {
    var list = getApplied();
    if (list.indexOf(name) === -1) { list.push(name); ss(APPLY_KEY, JSON.stringify(list)); }
    return list;
  }
  function push(obj) { try { (window.dataLayer = window.dataLayer || []).push(obj); } catch (e) {} }

  /* ---------- Блок над сіткою ---------- */
  var boost = document.createElement('div');
  boost.className = 'apply-boost';
  boost.innerHTML =
    '<div class="ab-head"><span class="ab-title">📈 Як збільшити шанс отримати гроші?</span>' +
    '<span class="ab-count">Обрано: <b class="ab-c">0</b> / 3</span></div>' +
    '<div class="ab-steps">' +
      '<div class="ab-step" data-step="1"><span class="ab-n">1 заявка</span><b>Базовий шанс</b></div>' +
      '<div class="ab-step" data-step="2"><span class="ab-n">2 заявки</span><b>Вищий шанс</b></div>' +
      '<div class="ab-step" data-step="3"><span class="ab-n">3 заявки</span><b>Найвищий шанс</b></div>' +
    '</div>' +
    '<p class="ab-note">📌 Кожна МФО ухвалює рішення окремо. Подайте заявку одразу в 2–3 компанії — так більше шансів, що хоча б одна схвалить потрібну суму.</p>';
  grid.parentNode.insertBefore(boost, grid);

  /* ---------- Липка панель ---------- */
  var bar = document.createElement('div');
  bar.className = 'apply-bar';
  bar.setAttribute('aria-live', 'polite');
  bar.innerHTML = '<div class="apply-bar-inner"><span class="apb-chance">📈 Шанс <b class="apb-c">0/3</b></span>' +
    '<span class="apb-text"></span><span class="apb-slots"></span></div>';
  document.body.appendChild(bar);

  /* ---------- Нижня панель ТОП-3 ---------- */
  var dock = document.createElement('div');
  dock.className = 'top3-dock';
  dock.setAttribute('aria-label', 'ТОП-3 пропозиції сьогодні');
  dock.innerHTML = '<div class="t3d-head"><span class="t3d-title">🔥 ТОП-3 пропозиції сьогодні</span>' +
    '<button class="t3d-close" type="button" aria-label="Закрити">×</button></div><div class="t3d-grid"></div>';
  document.body.appendChild(dock);
  var dockGrid = dock.querySelector('.t3d-grid');

  function updateUI(bump) {
    var list = getApplied(), n = list.length, shown = Math.min(n, GOAL);
    boost.querySelector('.ab-c').textContent = shown;
    boost.querySelectorAll('.ab-step').forEach(function (s) { s.classList.toggle('is-done', n >= Number(s.dataset.step)); });
    bar.querySelector('.apb-c').textContent = shown + '/' + GOAL;
    bar.querySelector('.apb-text').textContent = TEXTS[Math.min(n, 3)];
    var html = '';
    for (var i = 0; i < GOAL; i++) {
      html += list[i] ? '<span class="apb-slot is-filled" title="' + esc(list[i]) + '">✓ ' + esc(list[i]) + '</span>'
                      : '<span class="apb-slot" data-empty="1">МФО #' + (i + 1) + '</span>';
    }
    bar.querySelector('.apb-slots').innerHTML = html;
    var set = {};
    list.forEach(function (x) { set[x] = 1; });
    grid.querySelectorAll('.offer-card[data-mfo]').forEach(function (c) { c.classList.toggle('is-applied', !!set[c.dataset.mfo]); });
    dockGrid.querySelectorAll('.t3d-item').forEach(function (c) { c.classList.toggle('is-applied', !!set[c.dataset.mfo]); });
    if (bump) { bar.classList.remove('bump'); void bar.offsetWidth; bar.classList.add('bump'); }
  }

  function onApply(name, source) {
    if (!name) return;
    var before = getApplied().length;
    var list = addApplied(name);
    if (list.length !== before) {
      updateUI(true);
      push({ event: 'multi_apply_add', mfo_name: name, apply_count: list.length, source: source, page_path: location.pathname });
    } else {
      updateUI(false);
    }
  }

  /* ---------- Доповнення карток, коли сторінка їх намалювала ---------- */
  function enhance() {
    var cards = grid.querySelectorAll('.offer-card');
    cards.forEach(function (card, i) {
      if (card.dataset.obDone) return;
      var btn = card.querySelector('.offer-btn');
      var img = card.querySelector('.offer-logo-wrap img');
      var name = (btn && btn.getAttribute('data-offer')) || (img && img.getAttribute('alt')) || '';
      card.dataset.obDone = '1';
      card.dataset.mfo = name;
      var head = document.createElement('div');
      head.className = 'ob-head';
      head.innerHTML = '<span class="ob-rank">#' + String(i + 1).padStart(2, '0') + '</span>';
      card.insertBefore(head, card.firstChild);
      var logo = card.querySelector('.offer-logo-wrap');
      if (logo && name) {
        var nm = document.createElement('div');
        nm.className = 'ob-name';
        nm.textContent = name;
        logo.insertAdjacentElement('afterend', nm);
      }
      if (btn) {
        var note = document.createElement('div');
        note.className = 'ob-applied';
        note.textContent = '✓ Заявку подано';
        btn.insertAdjacentElement('beforebegin', note);
        btn.classList.add('ob-3d'); // стрілка малюється через CSS ::after — текст кнопки не змінюється (тригери GTM)
      }
    });
    if (cards.length) updateUI(false);
  }
  new MutationObserver(enhance).observe(grid, { childList: true });
  enhance();

  grid.addEventListener('click', function (e) {
    var btn = e.target.closest('.offer-btn');
    if (!btn) return;
    var card = btn.closest('.offer-card');
    onApply(card && card.dataset.mfo, 'grid');
  });
  dock.addEventListener('click', function (e) {
    if (e.target.closest('.t3d-close')) { ss(DOCK_KEY, '1'); sync(); return; }
    var btn = e.target.closest('.t3d-cta');
    if (!btn) return;
    var item = btn.closest('.t3d-item');
    onApply(item && item.dataset.mfo, 'top3_dock');
  });
  bar.addEventListener('click', function (e) {
    if (e.target.closest('[data-empty]')) {
      var t = document.querySelector('.offers-section') || grid;
      t.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });

  /* ---------- Дані для нижньої панелі (той самий фід, що й картки) ---------- */
  fetch('/mfo-live-data.json', { cache: 'no-store' })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      var offers = data.offers || [];
      var items = DOCK_MFO.map(function (n) { return offers.filter(function (o) { return o.name === n; })[0]; }).filter(Boolean);
      dockGrid.innerHTML = items.map(function (o, i) {
        return '<div class="t3d-item' + (i === 0 ? ' is-first' : '') + '" data-mfo="' + esc(o.name) + '">' +
          '<span class="t3d-label">' + DOCK_LABELS[i] + '</span>' +
          '<span class="t3d-logo"><img src="' + esc(o.logo) + '" alt="' + esc(o.name) + '" loading="lazy" onerror="this.style.display=\'none\'"></span>' +
          '<span class="t3d-meta">до ' + fmt(o.sum) + ' ₴ <span>· до ' + o.term + ' дн.</span></span>' +
          '<a class="offer-btn t3d-cta" href="' + esc(o.ref) + '" data-offer="' + esc(o.name) + '" data-pos="top3-' + (i + 1) + '" target="_blank" rel="sponsored nofollow noopener noreferrer">Оформити ↗</a>' +
        '</div>';
      }).join('');
      updateUI(false);
      sync();
    })
    .catch(function () {});

  /* ---------- Видимість панелей ---------- */
  var section = grid.closest('.offers-section') || grid;
  var header = document.getElementById('main-header');
  function sync() {
    var hb = header ? Math.max(0, header.getBoundingClientRect().bottom) : 68;
    bar.style.top = hb + 'px';
    var menuOpen = !!document.querySelector('#mobile-nav.open, .mobile-nav.open');
    var r = section.getBoundingClientRect();
    var inGrid = r.top < hb + 40 && r.bottom > window.innerHeight * 0.5;
    bar.classList.toggle('is-visible', inGrid && !menuOpen);
    var scrolled = window.scrollY > window.innerHeight * 0.8;
    var nearFooter = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 400;
    var showDock = !menuOpen && scrolled && !nearFooter && ss(DOCK_KEY) !== '1' && dockGrid.children.length > 0;
    dock.classList.toggle('is-visible', showDock);
  }
  window.addEventListener('scroll', sync, { passive: true });
  window.addEventListener('resize', sync);
  updateUI(false);
  sync();
})();
