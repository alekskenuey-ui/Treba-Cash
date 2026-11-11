/* TREBA CASH — SmartLink: рекламний банер угорі сторінок блогу, пропозицій і рейтингів.
 * Вставляється одразу після hero-блоку; посилання дописується мітками utm.js. */
(function () {
  'use strict';
  var URL_ = 'https://track-pdlp.com/ml?affid=62311';
  var path = location.pathname;
  var m = path.match(/^\/(blog|propozytsiyi|reytynhy)(\/|$)/);
  if (!m || document.getElementById('smartlink-banner')) return;
  var type = m[1];
  var slug = path.replace(/^\/|\/$/g, '').replace(/\//g, '_').slice(0, 60);

  function build() {
    var main = document.getElementById('main') || document.querySelector('main');
    if (!main) return;
    var wrap = document.createElement('div');
    wrap.className = 'container slb-wrap';
    wrap.id = 'smartlink-banner';
    wrap.innerHTML =
      '<div class="slb">' +
        '<span class="slb-tag">Партнерська добірка на основі даних та ШІ</span>' +
        '<img class="slb-logo" src="/assets/smartlink-logo.webp" alt="TREBA CASH SmartLink" width="640" height="360" loading="lazy">' +
        '<div>' +
          '<div class="slb-title">SmartLink: пропозиція, підібрана саме для вас</div>' +
          '<p class="slb-lead">Не хочете перебирати весь список? SmartLink автоматично підбирає пропозицію під ваш регіон та на основі ваших параметрів користувача й актуальних показників партнера.</p>' +
          '<ul class="slb-points"><li>Підбір за регіоном і свіжими даними</li><li>Один перехід замість довгого пошуку</li><li>Для вас безкоштовно</li></ul>' +
          '<p class="slb-note">Реклама. Рішення про видачу позики приймає фінансова установа; умови та вартість перевіряйте на сайті партнера перед оформленням.</p>' +
          '<a class="slb-btn" href="' + URL_ + '" target="_blank" rel="sponsored nofollow noopener noreferrer">Подати заявку →</a>' +
        '</div>' +
      '</div>';
    var hero = main.querySelector(':scope > header.hero, :scope > .hero') || main.querySelector('header.hero');
    if (hero && hero.parentNode === main) hero.insertAdjacentElement('afterend', wrap);
    else main.insertAdjacentElement('afterbegin', wrap);
    wrap.querySelector('.slb-btn').addEventListener('click', function () {
      try {
        if (typeof fbq === 'function') fbq('trackCustom', 'go_to_offer', { mfo: 'SmartLink', source: 'smartlink_banner_' + type });
        (window.dataLayer = window.dataLayer || []).push({ event: 'smartlink_click', placement: 'banner_' + type, page: slug });
      } catch (e) {}
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build); else build();
})();
