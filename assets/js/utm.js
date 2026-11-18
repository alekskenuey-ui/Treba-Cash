/* TREBA CASH — атрибуція трафіку та UTM для партнерських посилань.
 * Визначає канал при першому заході (першочергово — вхідні UTM/click-id),
 * зберігає на сесію і дописує мітки до посилань на PDL-Profit у момент кліку,
 * тому працює і для карток, які рендеряться з mfo-live-data.json.
 * Додаткові вхідні мітки (utm_creative, utm_adposition, utm_device, subid…) передаються як є. */
(function () {
  'use strict';
  var KEY = 'tc_attr';
  var PARTNER = /(^|\.)(pdl-profit\.com|track-pdlp\.com)$/i;
  var CLICK_IDS = ['gclid', 'gbraid', 'wbraid', 'fbclid', 'ttclid', 'msclkid'];
  var UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'];
  // Усі інші вхідні мітки (utm_creative, utm_adposition, utm_device, utm_keyword, subid1…) теж передаємо в партнерку
  var PASS = /^(utm_[a-z0-9_]+|sub(id)?\d*|aff_sub\d*)$/i;
  var SEARCH = { 'google': 'google', 'bing': 'bing', 'yahoo': 'yahoo', 'duckduckgo': 'duckduckgo', 'yandex': 'yandex', 'ukr.net': 'ukr_net', 'ecosia': 'ecosia' };
  var SOCIAL = { 'facebook': 'facebook', 'instagram': 'instagram', 't.me': 'telegram', 'telegram': 'telegram', 'viber': 'viber', 'tiktok': 'tiktok', 'youtube': 'youtube' };

  function store(get, set) { try { return get ? sessionStorage.getItem(KEY) : sessionStorage.setItem(KEY, set); } catch (e) { return null; } }

  function pageSlug() {
    var p = location.pathname.replace(/^\/|\/$/g, '');
    return (p || 'home').replace(/\//g, '_').slice(0, 60);
  }

  function host(ref) { try { return new URL(ref).hostname.replace(/^www\./, ''); } catch (e) { return ''; } }

  function match(table, h) {
    for (var k in table) if (h === k || h.indexOf(k) !== -1) return table[k];
    return '';
  }

  function detect() {
    var q = new URLSearchParams(location.search);
    var a = {};
    UTM_KEYS.forEach(function (k) { if (q.get(k)) a[k] = q.get(k); });
    CLICK_IDS.forEach(function (k) { if (q.get(k)) a[k] = q.get(k); });
    var extra = {};
    q.forEach(function (v, k) { if (v && PASS.test(k) && UTM_KEYS.indexOf(k) === -1) extra[k] = v.slice(0, 200); });
    a.extra = extra;

    if (!a.utm_source) {
      var h = host(document.referrer);
      var own = h === location.hostname.replace(/^www\./, '');
      if (a.gclid || a.gbraid || a.wbraid) { a.utm_source = 'google'; a.utm_medium = a.utm_medium || 'cpc'; a.utm_campaign = a.utm_campaign || 'google_ads'; }
      else if (a.fbclid) { a.utm_source = 'facebook'; a.utm_medium = a.utm_medium || 'cpc'; a.utm_campaign = a.utm_campaign || 'meta_ads'; }
      else if (a.msclkid) { a.utm_source = 'bing'; a.utm_medium = 'cpc'; a.utm_campaign = 'bing_ads'; }
      else if (h && !own && match(SEARCH, h)) { a.utm_source = match(SEARCH, h); a.utm_medium = 'organic'; a.utm_campaign = 'seo'; }
      else if (h && !own && match(SOCIAL, h)) { a.utm_source = match(SOCIAL, h); a.utm_medium = 'social'; a.utm_campaign = 'referral'; }
      else if (h && !own) { a.utm_source = h; a.utm_medium = 'referral'; a.utm_campaign = 'referral'; }
      else { a.utm_source = 'direct'; a.utm_medium = 'none'; a.utm_campaign = 'direct'; }
    }
    a.landing = pageSlug();
    return a;
  }

  var attr;
  try { attr = JSON.parse(store(true) || 'null'); } catch (e) { attr = null; }
  // Перший дотик зберігаємо; новий вхід із міткою/click-id перезаписує його
  var q0 = new URLSearchParams(location.search);
  var fresh = UTM_KEYS.concat(CLICK_IDS).some(function (k) { return q0.get(k); }) ||
    Array.from(q0.keys()).some(function (k) { return PASS.test(k); });
  if (!attr || fresh) { attr = detect(); store(false, JSON.stringify(attr)); }

  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push({
    event: 'traffic_attribution',
    traffic_channel: attr.utm_medium + '/' + attr.utm_source,
    traffic_source: attr.utm_source, traffic_medium: attr.utm_medium,
    traffic_campaign: attr.utm_campaign, landing_page: attr.landing
  });

  function decorate(a) {
    if (!a || !a.href) return;
    var u;
    try { u = new URL(a.href, location.href); } catch (e) { return; }
    if (!PARTNER.test(u.hostname)) return;
    function put(k, v) { if (v && !u.searchParams.has(k)) u.searchParams.set(k, v); }
    // PDL-Profit приймає лише: subid…subid10, utm_source, utm_medium, utm_campaign, utm_term,
    // utm_creative, utm_adgroup, utm_device, utm_adposition, gclid. utm_content він не зберігає,
    // тому сторінки та позицію передаємо в subid (subid3 і utm_device вже ставить GTM — їх не чіпаємо).
    put('utm_source', attr.utm_source);
    put('utm_medium', attr.utm_medium);
    put('utm_campaign', attr.utm_campaign);
    put('utm_term', attr.utm_term);
    put('subid', attr.landing);                       // сторінка входу на сайт
    put('subid2', pageSlug());                        // сторінка, з якої клікнули на офер
    put('subid4', attr.utm_content);                  // utm_content з реклами (оголошення/креатив)
    put('subid5', a.getAttribute('data-pos') || (a.closest && a.closest('[data-pos]') ? a.closest('[data-pos]').getAttribute('data-pos') : ''));  // позиція оферу
    CLICK_IDS.forEach(function (k) { put(k, attr[k]); });
    var ex = attr.extra || {};
    for (var k in ex) put(k, ex[k]);
    u.searchParams.delete('utm_content');
    a.href = u.toString();
  }

  // SEO-сторінки віддають посилання на офери як href="#" data-go="…", щоб роботи без JS
  // не ходили по них і не накручували «уніки» в PDL-Profit. Людям справжнє посилання
  // підставляємо одразу після завантаження (і про всяк випадок — у момент кліку).
  function activate(a) {
    var go = a && a.getAttribute && a.getAttribute('data-go');
    if (!go) return;
    try { if (PARTNER.test(new URL(go, location.href).hostname) && a.getAttribute('href') !== go) a.setAttribute('href', go); } catch (e) {}
  }
  function activateAll() {
    var list = document.querySelectorAll('a[data-go]');
    for (var i = 0; i < list.length; i++) activate(list[i]);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', activateAll);
  else activateAll();

  function handler(e) {
    var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    activate(a);
    decorate(a);
  }
  ['mousedown', 'touchstart', 'keydown', 'contextmenu', 'click'].forEach(function (t) {
    document.addEventListener(t, handler, true);
  });
})();
