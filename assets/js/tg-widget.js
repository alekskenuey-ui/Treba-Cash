/* TREBA CASH — Telegram-віджет: бічна картка (десктоп) і кнопка-плашка (мобільний).
 * Розмітка вставляється звідси, тож текст CTA змінюється в одному місці.
 * Дані «оновлено / N МФО» — реальні, з /mfo-live-data.json. Жодних вигаданих лічильників. */
(function () {
  'use strict';
  var BOT_URL = 'https://t.me/trebacash_bot';
  var SKIP = ['/privacy-policy/', '/terms/', '/contact/', '/about/', '/quiz/', '/porivnyannya-mfo/'];
  var p = location.pathname.replace(/index\.html$/, '');
  if (SKIP.indexOf(p) !== -1) return;

  var ICON = '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M21.5 3.5L2.75 10.9c-1.2.47-1.19 1.13-.22 1.42l4.8 1.5 1.85 5.7c.22.62.37.87.76.87.34 0 .5-.16.7-.36l1.94-1.9 4.03 2.97c.74.41 1.28.2 1.47-.68l2.66-12.55c.28-1.08-.4-1.57-1.24-1.24z" fill="#fff"/></svg>';
  var isMobile = function () { return window.matchMedia('(max-width:900px)').matches; };
  function ss(k, v) { try { if (v === undefined) return sessionStorage.getItem(k); if (v === null) sessionStorage.removeItem(k); else sessionStorage.setItem(k, v); } catch (e) {} return null; }
  function push(o) { try { (window.dataLayer = window.dataLayer || []).push(o); } catch (e) {} }

  var root = document.createElement('div');
  root.innerHTML =
    '<a id="tgx-fab" class="is-hidden" href="' + BOT_URL + '" target="_blank" rel="noopener" aria-label="Підібрати МФО в Telegram">' +
      '<span class="tgx-fab-icon">' + ICON + '</span>' +
      '<span class="tgx-fab-text"><span class="tgx-fab-title">Підібрати МФО під вас</span><span class="tgx-fab-sub">Telegram · безкоштовно · ~1 хв</span></span></a>' +
    '<aside id="tgx-widget" aria-label="Підбір МФО в Telegram">' +
      '<button type="button" class="tgx-tab" id="tgx-tab" aria-label="Відкрити підбір МФО"><span>Підбір МФО</span></button>' +
      '<div class="tgx-card">' +
        '<button type="button" class="tgx-close" id="tgx-close" aria-label="Закрити">✕</button>' +
        '<div class="tgx-icon-row"><div class="tgx-icon"><span class="ping"></span>' + ICON + '</div>' +
          '<div class="tgx-live" id="tgx-live"><span class="d"></span><span id="tgx-live-text"></span></div></div>' +
        '<p class="tgx-headline">Не знаєте, яку МФО обрати?</p>' +
        '<p class="tgx-sub">Відповідайте на кілька запитань у Telegram і отримайте <b>добірку МФО під вашу суму та строк</b>. Рішення завжди залишається за вами.</p>' +
        '<a href="' + BOT_URL + '" class="tgx-cta" id="tgx-cta" target="_blank" rel="noopener">' + ICON + 'Підібрати МФО в Telegram</a>' +
        '<p class="tgx-fine">Близько хвилини · безкоштовно · рішення про видачу ухвалює МФО</p>' +
      '</div></aside>';
  while (root.firstChild) document.body.appendChild(root.firstChild);

  var widget = document.getElementById('tgx-widget'), fab = document.getElementById('tgx-fab');
  var mobileNav = document.getElementById('mobile-nav');

  // Клік по реальній партнерській пропозиції — більше не відволікаємо відвідувача
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href*="pdl-profit.com"]');
    if (a) ss('tgxOfferClicked', '1');
  }, true);

  // Реальні дані: скільки МФО у порівнянні й коли їх оновлено
  fetch('/mfo-live-data.json', { cache: 'force-cache' }).then(function (r) { return r.json(); }).then(function (d) {
    if (!d || !d.count || !d.generatedAt) return;
    var dt = new Date(d.generatedAt); if (isNaN(dt)) return;
    var day = dt.toLocaleDateString('uk-UA', { day: 'numeric', month: 'long' });
    document.getElementById('tgx-live-text').textContent = d.count + ' МФО в порівнянні · оновлено ' + day;
    document.getElementById('tgx-live').classList.add('is-on');
  }).catch(function () {});

  function click(src) { return function () { push({ event: 'tg_click', tg_source: src, page_path: p }); }; }
  document.getElementById('tgx-cta').addEventListener('click', click('desktop_widget'));
  fab.addEventListener('click', click('mobile_fab'));

  function canShow() { return !ss('tgxClosed') && !ss('tgxOfferClicked') && !isMobile(); }
  function reveal() { if (!canShow() || widget.classList.contains('is-visible')) return; widget.classList.add('is-visible'); push({ event: 'tg_widget_view', page_path: p }); }
  function onScroll() { if (window.scrollY > 400) { reveal(); window.removeEventListener('scroll', onScroll); } }
  window.addEventListener('scroll', onScroll, { passive: true });
  setTimeout(reveal, 12000);

  document.getElementById('tgx-close').addEventListener('click', function () { widget.classList.add('is-collapsed'); ss('tgxClosed', '1'); });
  document.getElementById('tgx-tab').addEventListener('click', function () { widget.classList.remove('is-collapsed'); ss('tgxClosed', null); });
  if (ss('tgxClosed')) { widget.classList.add('is-visible', 'is-collapsed'); }

  // Мобільна плашка: ховається біля футера, при відкритому меню та вводі в поле
  function fabHide() {
    if (!isMobile() || ss('tgxOfferClicked')) return true;
    if (mobileNav && mobileNav.classList.contains('open')) return true;
    var a = document.activeElement;
    if (a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) return true;
    return window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 160;
  }
  function updateFab() { fab.classList.toggle('is-hidden', fabHide()); }
  window.addEventListener('scroll', updateFab, { passive: true });
  window.addEventListener('resize', updateFab);
  document.addEventListener('focusin', updateFab);
  document.addEventListener('focusout', function () { setTimeout(updateFab, 50); });
  if (mobileNav) new MutationObserver(updateFab).observe(mobileNav, { attributes: true, attributeFilter: ['class'] });
  updateFab();
})();
