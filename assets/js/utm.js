/* TREBA CASH — атрибуція трафіку та UTM для партнерських посилань.
 * Визначає канал при першому заході (першочергово — вхідні UTM/click-id),
 * зберігає на сесію і дописує мітки до посилань на PDL-Profit у момент кліку,
 * тому працює і для карток, які рендеряться з mfo-live-data.json. */
(function () {
  'use strict';
  var KEY = 'tc_attr';
  var PARTNER = /(^|\.)(pdl-profit\.com|track-pdlp\.com)$/i;
  var CLICK_IDS = ['gclid', 'gbraid', 'wbraid', 'fbclid', 'ttclid', 'msclkid'];
  var UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'];
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
  var fresh = UTM_KEYS.concat(CLICK_IDS).some(function (k) { return q0.get(k); });
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
    put('utm_source', attr.utm_source);
    put('utm_medium', attr.utm_medium);
    put('utm_campaign', attr.utm_campaign);
    // utm_content: творчість із реклами, інакше сторінка, з якої зроблено клік
    put('utm_content', attr.utm_content || ('p_' + pageSlug()));
    put('utm_term', attr.utm_term);
    CLICK_IDS.forEach(function (k) { put(k, attr[k]); });
    a.href = u.toString();
  }

  function handler(e) {
    var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    decorate(a);
  }
  ['mousedown', 'touchstart', 'keydown', 'contextmenu', 'click'].forEach(function (t) {
    document.addEventListener(t, handler, true);
  });
})();
