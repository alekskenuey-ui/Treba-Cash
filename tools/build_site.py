#!/usr/bin/env python3
"""TREBA CASH — щоденна збірка SEO-частини сайту з фіду PDL-Profit.

Запускається GitHub Action після fetch_offers.py (див. .github/workflows/update-offers.yml).
Скрипт ідемпотентний: повторний запуск без змін у фіді нічого не змінює.

Що робить:
  1. Вшиває картки оферів у HTML сторінок із #offers-grid (серверний рендер),
     щоб Google бачив офери без JavaScript (JSON закрито в robots.txt).
  2. Замінює важкий блок «Реквізити партнерів» на компактний — лише МФО,
     показані на сторінці; повні реквізити — на /rekvizyty-partneriv/.
  3. Генерує сторінки МФО-брендів /mfo/<slug>/, каталог /mfo/ і /rekvizyty-partneriv/.
  4. Футер НЕ змінює (вимога власника: футер однаковий на всіх сторінках).
  5. Після 1 січня замінює минулий рік на поточний у title/H1/og-title.
  6. Перебудовує sitemap.xml: лише індексовані сторінки, lastmod змінюється,
     тільки коли змінився вміст сторінки.

Вітрину /porivnyannya-mfo/ (лендинг Google Ads) і FB/KZ/MX-лендинги скрипт НЕ чіпає.

Запуск локально:  python3 tools/build_site.py
"""
import datetime
import hashlib
import html
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SITE = 'https://trebacash.site'
TODAY = datetime.date.today()
STATE_FILE = os.path.join(ROOT, 'tools', 'build-state.json')

# Сторінки, які скрипт не змінює (рекламні лендинги, тест, інші країни)
PROTECTED = ('porivnyannya-mfo/', 'porivnyannya-mfo-fb/', 'porivnyannya-mfo-kz/', 'porivnyannya-mfo-mx/',
             'test/', 'go/', 'quiz-fb/', 'quiz-tg-fb/', 'quiz-to-fb/')
CARDS_DEFAULT = 12
# Фільтр карток для сторінок «за сумою»: мінімальний ліміт МФО
SUM_FILTER = {'propozytsiyi/kredyt-na-5000-grn/': 5000, 'propozytsiyi/kredyt-na-10000-grn/': 10000,
              'propozytsiyi/kredyt-na-20000-grn/': 20000}
SHELL = 'propozytsiyi/kredyt-cherez-diyu/index.html'   # сторінка-оболонка для генерованих сторінок
# Брендовий трафік: поки менеджер PDL-Profit не підтвердив, що органіка по бренду дозволена,
# сторінки /mfo/<бренд>/ закриті від індексу. Щоб відкрити — постав True.
BRAND_PAGES_INDEX = False
LEGAL_DAILY_MAX = 1.0   # % на день, Закон №3498-IX (з 20.08.2024)

esc = lambda s: html.escape(str(s if s is not None else ''), quote=True)


def rd(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return f.read()


def wr(p, s):
    full = os.path.join(ROOT, p)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    old = None
    if os.path.exists(full):
        with open(full, encoding='utf-8') as f:
            old = f.read()
    if old != s:
        with open(full, 'w', encoding='utf-8') as f:
            f.write(s)
        return True
    return False


def fmt(n):
    return f'{int(round(n)):,}'.replace(',', ' ')


def money(x):
    if abs(x - round(x)) < 0.005:
        return fmt(x)
    return f'{x:,.2f}'.replace(',', ' ').replace('.', ',')


def pct(x):
    s = f'{x:.2f}'.rstrip('0').rstrip('.')
    return s.replace('.', ',')


# ------------------------------------------------------------------ дані
TRANSLIT = dict(zip('абвгґдеєжзиіїйклмнопрстуфхцчшщьюя',
                    ['a', 'b', 'v', 'h', 'g', 'd', 'e', 'ye', 'zh', 'z', 'y', 'i', 'yi', 'y', 'k', 'l', 'm', 'n', 'o', 'p',
                     'r', 's', 't', 'u', 'f', 'kh', 'ts', 'ch', 'sh', 'shch', '', 'yu', 'ya']))


def slugify(name):
    s = ''.join(TRANSLIT.get(c, c) for c in name.lower())
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s or 'mfo'


def load_offers():
    data = json.loads(rd('mfo-live-data.json'))
    try:
        req = json.loads(rd('requisites.json'))
    except FileNotFoundError:
        req = {}
    offers = []
    for i, o in enumerate(data.get('offers', [])):
        r = req.get(o['name'], {})
        o = dict(o)
        for k in ('legal', 'edrpou', 'address', 'phone', 'email'):
            if not o.get(k) and r.get(k):
                o[k] = r[k]
        o['slug'] = slugify(o['name'])
        o['pos'] = i + 1
        o['dmin'] = (o.get('rateMin') or 0) / 365
        o['dmax'] = (o.get('rateMax') or 0) / 365
        if o['dmin'] > o['dmax'] and o['dmax']:
            o['dmin'], o['dmax'] = o['dmax'], o['dmin']
        # Закон №3498-IX: з 20.08.2024 денна ставка не може перевищувати 1%.
        # Якщо фід показує більше (застарілі дані), не публікуємо цю цифру.
        o['dmin'] = round(min(o['dmin'], LEGAL_DAILY_MAX), 2)
        o['dmax'] = round(min(o['dmax'], LEGAL_DAILY_MAX), 2)
        offers.append(o)
    return data.get('generatedAt', ''), offers


def badge(o):
    if str(o.get('hasZeroBadge')).lower() == 'true':
        return o.get('goldBadgeText') or 'Акція для нових клієнтів'
    return o.get('badge') or 'Вигідні умови'


# ------------------------------------------------------------------ картки
def card_html(o, pos):
    return (f'<div class="offer-card">'
            f'<div class="offer-logo-wrap"><img src="{esc(o["logo"])}" alt="{esc(o["name"])}" loading="lazy" width="120" height="48" onerror="this.style.display=\'none\'"></div>'
            f'<div class="offer-badge">{esc(badge(o))}</div>'
            f'<div class="offer-stats"><div class="row">Макс. сума <b>до {fmt(o["sum"])} ₴</b></div>'
            f'<div class="row">На строк <b>до {o["term"]} дн.</b></div></div>'
            f'<a class="offer-btn" href="#" data-go="{esc(o["ref"])}" data-offer="{esc(o["name"])}" data-pos="{pos}" target="_blank" rel="sponsored nofollow noopener noreferrer">Отримати гроші</a>'
            f'<a class="offer-info" href="/mfo/{o["slug"]}/">Умови {esc(o["name"])}</a>'
            f'</div>')


def pick_offers(path, offers, n=CARDS_DEFAULT):
    lim = SUM_FILTER.get(path)
    lst = [o for o in offers if not lim or o['sum'] >= lim]
    return lst[:n]


def grid_html(cards):
    return '\n        ' + '\n        '.join(card_html(o, i + 1) for i, o in enumerate(cards)) + '\n      '


def requisites_compact(cards):
    rows = []
    for o in cards:
        legal = esc(o.get('legal') or 'дані уточнюються')
        ed = f', ЄДРПОУ {esc(o["edrpou"])}' if o.get('edrpou') else ''
        rows.append(f'<li><a href="/mfo/{o["slug"]}/">{esc(o["name"])}</a> — {legal}{ed}</li>')
    return ('<section class="requisites-section requisites-compact">\n'
            '      <h2 class="section-title">Реквізити МФО з цієї сторінки</h2>\n'
            '      <details><summary>Показати юридичні особи та ЄДРПОУ</summary><ul class="req-list">'
            + ''.join(rows) +
            '</ul></details>\n      <p class="section-sub">Адреси, телефони та свідоцтва всіх партнерів — на сторінці '
            '<a href="/rekvizyty-partneriv/">реквізити партнерів</a>. Статус компанії перевіряй у '
            '<a href="https://kis.bank.gov.ua/" target="_blank" rel="noopener">реєстрі НБУ</a>.</p>\n    </section>')


LOADER_HELPER = ('<script>function tcOffersFetch(u,o){var g=document.getElementById(\'offers-grid\');'
                 'return (g&&g.dataset.ssr)?new Promise(function(){}):fetch(u,o);}</script>')
CARD_CSS = ('<style>.offer-info{display:block;text-align:center;font-size:12.5px;margin-top:8px;color:inherit;opacity:.75}'
            '.requisites-compact details{margin-top:12px}.requisites-compact summary{cursor:pointer;font-weight:600}'
            '.req-list{columns:2;font-size:14px;margin-top:10px}@media(max-width:640px){.req-list{columns:1}}</style>')


def ssr_page(path, s, offers):
    """Серверний рендер оферів + компактні реквізити на одній сторінці."""
    m = re.search(r'(<div class="offers-grid" id="offers-grid")([^>]*)>(.*?)(</div>\s*<div class="offers-more">)', s, re.S)
    if not m:
        return s
    cards = pick_offers(path, offers)
    s = s[:m.start()] + m.group(1) + ' data-ssr="1">' + grid_html(cards) + m.group(4) + s[m.end():]
    s = re.sub(r'<div class="offers-more"><a class="hl" href="/porivnyannya-mfo/">[^<]*</a></div>',
               f'<div class="offers-more"><a class="hl" href="/porivnyannya-mfo/">усі {len(offers)} пропозицій з фільтрами →</a></div>', s, count=1)
    # inline-завантажувачі: не перемальовувати SSR-сітку
    s = s.replace("fetch('/mfo-live-data.json'", "tcOffersFetch('/mfo-live-data.json'")
    if 'function tcOffersFetch' not in s:
        s = s.replace('</head>', LOADER_HELPER + '\n' + CARD_CSS + '\n</head>', 1)
    # реквізити
    s = re.sub(r'<section class="requisites-section[^"]*">.*?</section>', lambda _: requisites_compact(cards), s, count=1, flags=re.S)
    return s


# ------------------------------------------------------------------ преміум-оформлення
PREMIUM_TAGS = ('<link rel="stylesheet" href="/assets/css/premium.css">\n'
                '<script src="/assets/js/premium.js" defer></script>\n')


def premium(s):
    """Підключає преміум-шар оформлення (не на рекламних лендингах — їх main() пропускає)."""
    if '/assets/css/premium.css' in s or '</head>' not in s:
        return s
    return s.replace('</head>', PREMIUM_TAGS + '</head>', 1)


# ------------------------------------------------------------------ рік у заголовках
def bump_year(s):
    y, prev = TODAY.year, TODAY.year - 1
    if y <= 2026:
        return s
    def rep(m):
        return m.group(0).replace(str(prev), str(y))
    s = re.sub(r'<title>.*?</title>', rep, s, flags=re.S)
    s = re.sub(r'<h1[^>]*>.*?</h1>', rep, s, flags=re.S)
    s = re.sub(r'<meta (?:property|name)="(?:og|twitter):title" content="[^"]*"', rep, s)
    s = re.sub(r'"(?:headline|name)": "[^"]*"', rep, s)
    return s


# ------------------------------------------------------------------ генеровані сторінки
def shell_parts():
    s = rd(SHELL)
    head_top = s[:s.index('<meta name="robots"')]
    style = re.search(r'<style>.*?</style>', s, re.S).group(0)
    assets = s[s.index('</style>') + len('</style>'):s.index('</head>')]
    assets = re.sub(r'<script>function tcOffersFetch.*?</script>\s*', '', assets, flags=re.S)
    assets = re.sub(r'<style>\.offer-info.*?</style>\s*', '', assets, flags=re.S)
    body_top = s[s.index('<body>'):s.index('<main id="main">')]
    footer = s[s.index('<footer'):s.index('</footer>') + len('</footer>')]
    return head_top, style, assets, body_top, footer


def ld_json(path, title, h1, desc, crumbs, faqs, kind='WebPage', date=None):
    url = SITE + path
    graph = [
        {"@type": "Organization", "@id": f"{SITE}/#organization", "name": "TREBA CASH", "url": f"{SITE}/",
         "logo": {"@type": "ImageObject", "url": f"{SITE}/assets/logo-icon.png"}},
        {"@type": kind, "@id": url + "#webpage", "url": url, "name": h1, "description": desc, "inLanguage": "uk-UA",
         "isPartOf": {"@id": f"{SITE}/#website"}, "dateModified": date or TODAY.isoformat(),
         "publisher": {"@id": f"{SITE}/#organization"}},
        {"@type": "BreadcrumbList", "@id": url + "#breadcrumbs", "itemListElement": [
            dict({"@type": "ListItem", "position": i + 1, "name": n}, **({"item": SITE + u} if u else {}))
            for i, (n, u) in enumerate(crumbs)]},
    ]
    if faqs:
        graph.append({"@type": "FAQPage", "@id": url + "#faq", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": re.sub('<[^>]+>', '', a)}}
            for q, a in faqs]})
    return '<script type="application/ld+json">\n' + json.dumps({"@context": "https://schema.org", "@graph": graph},
                                                               ensure_ascii=False, indent=2) + '\n</script>'


def page(path, title, desc, h1, sub, crumbs, main_html, faqs=(), robots='index, follow, max-image-preview:large', label=''):
    head_top, style, assets, body_top, footer = shell_parts()
    url = SITE + path
    meta = f'''<meta name="robots" content="{robots}">
<meta name="theme-color" content="#27ae60">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<link rel="alternate" hreflang="uk" href="{url}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:image" content="{SITE}/assets/og-image.jpg">
<meta property="og:locale" content="uk_UA">
<meta property="og:site_name" content="TREBA CASH">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800;900&family=Unbounded:wght@700;900&display=swap" rel="stylesheet">
{ld_json(path, title, h1, desc, crumbs, list(faqs))}
'''
    bc = ' › '.join(f'<a href="{u}">{esc(n)}</a>' if u else esc(n) for n, u in crumbs)
    faq_block = ''
    if faqs:
        faq_block = ('<section class="faq-item-wrap" aria-labelledby="faq-title"><h2 id="faq-title">Поширені запитання</h2>'
                     + ''.join(f"<details class='faq-item'><summary>{esc(q)}</summary><p>{a}</p></details>" for q, a in faqs)
                     + '</section>')
    main = f'''<main id="main">
  <header class="hero">
    <div class="container">
      <nav class="breadcrumbs" aria-label="Хлібні крихти">{bc}</nav>
      {f'<span class="label">{esc(label)}</span>' if label else ''}
      <h1>{esc(h1)}</h1>
      <p class="sub">{sub}</p>
    </div>
  </header>
{main_html}
  <div class="article-wrap"><article class="article">
    {faq_block}
    <p class="disclaimer-small">Матеріал має інформаційний та рекламний характер і не є фінансовою консультацією. Рішення про видачу кредиту ухвалює МФО. TREBA CASH не є кредитором і отримує винагороду від партнерів за звернення через наші посилання.</p>
  </article></div>
</main>
'''
    script = '<script>window.addEventListener("scroll",function(){var h=document.getElementById("main-header");if(h)h.classList.toggle("scrolled",window.scrollY>10);});</script>'
    extra_css = ('<style>.kv{width:100%;border-collapse:collapse;margin:12px 0 20px}.kv th,.kv td{padding:10px 12px;border-bottom:1px solid rgba(0,0,0,.08);text-align:left;vertical-align:top}'
                 '.kv th{width:42%;font-weight:600}.notice{background:#fff7e6;border-left:4px solid #f5a623;padding:14px 18px;border-radius:10px;margin:0 0 22px}'
                 '.mfo-table{width:100%;border-collapse:collapse;font-size:14.5px}.mfo-table th,.mfo-table td{padding:9px 10px;border-bottom:1px solid rgba(0,0,0,.08);text-align:left}'
                 '.mfo-table th{background:rgba(39,174,96,.08)}.table-wrap{overflow-x:auto}'
                 '.law-facts{background:linear-gradient(135deg,rgba(39,174,96,.07),rgba(39,174,96,.02));border:1px solid rgba(39,174,96,.18);border-radius:20px;padding:22px 26px;margin:30px 0}'
                 '.law-facts li{margin:0 0 12px}.law-src{font-size:13.5px;opacity:.85}</style>')
    assets = assets if '/assets/css/premium.css' in assets else assets + PREMIUM_TAGS
    out = (head_top + meta + style + '\n' + extra_css + assets + LOADER_HELPER + '\n' + CARD_CSS + '\n</head>\n'
           + body_top + main + '\n' + footer + '\n' + script + '\n</body>\n</html>\n')
    return out


def offers_section(cards, title='Схожі пропозиції', note=''):
    return f'''  <div class="container">
    <section class="offers-section">
      <h2 class="offers-title">{esc(title)}</h2>
      <p class="offers-sub">{note or 'Дані оновлюються щодня автоматично'}</p>
      <div class="offers-grid" id="offers-grid" data-ssr="1">{grid_html(cards)}</div>
      <div class="offers-more"><a class="hl" href="/porivnyannya-mfo/">порівняти всі пропозиції з фільтрами →</a></div>
    </section>
  </div>'''


def similar(o, offers, n=6):
    others = [x for x in offers if x['name'] != o['name']]
    others.sort(key=lambda x: (abs(x['sum'] - o['sum']) / max(o['sum'], 1) + abs(x['term'] - o['term']) / 365, x['pos']))
    return others[:n]


def mfo_page(o, offers, generated):
    name = o['name']
    same_legal = [x for x in offers if x['name'] != name and o.get('edrpou') and x.get('edrpou') == o['edrpou']]
    promo = str(o.get('hasZeroBadge')).lower() == 'true'
    ex_sum = min(5000, o['sum'])
    ex_days = min(30, o['term'])
    rows = [('Максимальна сума', f'до {fmt(o["sum"])} ₴'),
            ('Максимальний строк', f'до {o["term"]} днів'),
            ('Денна ставка', (f'від {pct(o["dmin"])}% до {pct(o["dmax"])}%' + (' (законний максимум — 1%)' if o['dmax'] >= LEGAL_DAILY_MAX else '')) if o['dmax'] else 'уточнюється'),
            ('Акція для нових клієнтів', esc(o.get('goldBadgeText')) if promo else 'немає в поточних умовах'),
            ('Юридична особа (кредитор)', esc(o.get('legal') or 'дані уточнюються')),
            ('ЄДРПОУ', esc(o.get('edrpou') or '—')),
            ('Адреса', esc(o.get('address') or '—'))]
    if o.get('phone'):
        rows.append(('Телефон', esc(o['phone'])))
    if o.get('email'):
        rows.append(('Email', esc(o['email'])))
    kv = '<table class="kv">' + ''.join(f'<tr><th>{k}</th><td>{v}</td></tr>' for k, v in rows) + '</table>'

    cost = []
    if o['dmin'] and o['dmin'] < o['dmax']:
        kind = 'акційною (мінімальною)' if promo else 'мінімальною'
        cost.append(f'<li>За {kind} ставкою {pct(o["dmin"])}% на день: {fmt(ex_sum)} ₴ на {ex_days} днів — відсотки {money(ex_sum * o["dmin"] / 100 * ex_days)} ₴, до повернення {money(ex_sum + ex_sum * o["dmin"] / 100 * ex_days)} ₴.</li>')
    if o['dmax']:
        cost.append(f'<li>За {"максимальною" if o["dmin"] < o["dmax"] else "стандартною"} ставкою {pct(o["dmax"])}% на день: {fmt(ex_sum)} ₴ на {ex_days} днів — відсотки {money(ex_sum * o["dmax"] / 100 * ex_days)} ₴, до повернення {money(ex_sum + ex_sum * o["dmax"] / 100 * ex_days)} ₴.</li>')
    cost_html = ('<ul>' + ''.join(cost) + '</ul>') if cost else '<p>Ставки в поточному фіді не вказані — дивись умови на сайті кредитора.</p>'

    group = ''
    if same_legal:
        links = ', '.join(f'<a href="/mfo/{x["slug"]}/">{esc(x["name"])}</a>' for x in same_legal)
        group = (f'<h2>Інші бренди цього кредитора</h2><p>{esc(o["legal"])} працює також під брендами: {links}. '
                 f'Це одна юридична особа, тому кредитна історія та рішення в цих сервісах можуть бути повʼязані: '
                 f'відмова в одному бренді часто означає відмову і в іншому. Детальніше — у матеріалі '
                 f'<a href="/reytynhy/skilky-mfo-v-ukrayini-brendy-i-yurydychni-osoby/">хто насправді стоїть за брендами МФО</a>.</p>')

    notice = ''
    if o['slug'] == 'treba':
        notice = ('<div class="notice"><strong>Важливо:</strong> TREBA CASH — незалежний сервіс порівняння МФО і не є компанією Treba '
                  'чи її кредитором. Ми не маємо доступу до твого особистого кабінету, договору чи боргу. З питань погашення, '
                  'продовження, прострочення чи особистого кабінету звертайся безпосередньо до кредитора за реквізитами нижче.</div>')

    verify = (f'<p>Перед заявкою перевір, що {esc(o.get("legal") or "кредитор")} є в '
              f'<a href="https://kis.bank.gov.ua/" target="_blank" rel="noopener">Державному реєстрі фінансових установ НБУ</a>'
              + (f' — пошук за кодом ЄДРПОУ <strong>{esc(o["edrpou"])}</strong>.' if o.get('edrpou') else '.')
              + ' Як це зробити покроково — у матеріалі <a href="/propozytsiyi/yak-pereviryty-litsenziyu-mfo/">як перевірити ліцензію МФО</a>.</p>')

    body = f'''  <div class="container"><div class="intro-wide">
    {notice}
    <p class="lead">{esc(name)} — онлайн-кредит на картку до {fmt(o["sum"])} ₴ на строк до {o["term"]} днів. {esc(badge(o))}. Нижче — актуальні умови з фіду партнерської мережі (оновлено {esc(generated[:10])}), реквізити кредитора та приклад розрахунку вартості.</p>
    <p style="margin-top:14px"><a class="offer-btn" style="display:inline-block;max-width:320px" href="#" data-go="{esc(o["ref"])}" data-offer="{esc(name)}" data-pos="0" target="_blank" rel="sponsored nofollow noopener noreferrer">Перейти на сайт {esc(name)}</a></p>
  </div></div>
  <div class="article-wrap"><article class="article">
    <h2>Умови кредиту {esc(name)}</h2>
    {kv}
    <h2>Скільки коштує кредит у {esc(name)}</h2>
    <p>Відсотки нараховуються за фактичні дні користування: сума × денна ставка × кількість днів. Приклади для {fmt(ex_sum)} ₴ на {ex_days} днів:</p>
    {cost_html}
    <p>Це орієнтир. Точну ставку, реальну річну процентну ставку (РРПС) і суму до повернення показує паспорт споживчого кредиту — його кредитор зобовʼязаний надати до підписання договору. Що в ньому шукати — у матеріалі <a href="/blog/pasport-spozhyvchogo-kredytu/">паспорт споживчого кредиту</a>.</p>
    <h2>Як перевірити {esc(name)}</h2>
    {verify}
    {group}
    <h2>Якщо {esc(name)} відмовила</h2>
    <p>Кожна МФО має власний скоринг, тому відмова в одній компанії не означає відмову в іншій. Подай заявку в 2–3 МФО зі схожими умовами — нижче вони підібрані за сумою та строком. Але не бери кілька позик одночасно, якщо не впевнений, що повернеш усі. Чому відмовляють і що змінити — у матеріалі <a href="/propozytsiyi/chomu-mfo-vidmovlyayut-v-kredyti/">чому МФО відмовляють у кредиті</a>.</p>
  </article></div>
{offers_section(similar(o, offers), f'Схожі на {name} пропозиції')}'''
    faqs = [(f'Хто кредитор {name}?', f'{esc(o.get("legal") or "Дані про юридичну особу уточнюються")}' + (f', код ЄДРПОУ {esc(o["edrpou"])}.' if o.get('edrpou') else '.')),
            (f'Яку максимальну суму дає {name}?', f'До {fmt(o["sum"])} ₴. Новим клієнтам МФО часто схвалює меншу суму, а ліміт збільшує після вчасного повернення.'),
            (f'На який строк можна взяти кредит у {name}?', f'До {o["term"]} днів за поточними умовами.')]
    if promo:
        faqs.append((f'Чи є в {name} акція для нових клієнтів?', f'Так: {esc(o.get("goldBadgeText") or "акційна ставка")}. Акція зазвичай діє лише на першу позику та обмежена за строком — уточнюй у договорі.'))
    if o['slug'] == 'treba':
        faqs.append(('Чи TREBA CASH — це Treba?', 'Ні. TREBA CASH — незалежний сервіс порівняння МФО. З питань кабінету, погашення чи боргу звертайся безпосередньо до кредитора.'))
    title = f'{name}: умови кредиту, ставки та реквізити кредитора | TREBA CASH'
    if len(title) > 70:
        title = f'{name}: умови кредиту та реквізити | TREBA CASH'
    desc = (f'{name} — кредит онлайн до {fmt(o["sum"])} ₴ на {o["term"]} днів. Ставки, приклад розрахунку, '
            f'юридична особа та ЄДРПОУ, як перевірити в реєстрі НБУ і схожі пропозиції.')
    return page(f'/mfo/{o["slug"]}/', title, desc, f'{name}: умови кредиту онлайн, ставки та реквізити',
                f'Оновлено {esc(generated[:10])} з даних партнерської мережі', [('Головна', '/'), ('Усі МФО', '/mfo/'), (name, None)],
                body, faqs, label='Огляд МФО',
                robots='index, follow, max-image-preview:large' if BRAND_PAGES_INDEX else 'noindex, follow')


def mfo_index(offers, generated):
    rows = ''.join(f'<tr><td><a href="/mfo/{o["slug"]}/">{esc(o["name"])}</a></td><td>до {fmt(o["sum"])} ₴</td><td>до {o["term"]} дн.</td>'
                   f'<td>{"від " + pct(o["dmin"]) + "%" if o["dmax"] else "—"}</td><td>{esc(o.get("legal") or "—")}</td></tr>' for o in offers)
    body = f'''  <div class="container"><div class="intro-wide">
    <p class="lead">Каталог {len(offers)} МФО, з якими працює TREBA CASH: максимальна сума, строк, мінімальна денна ставка та юридична особа кредитора. Натисни на назву, щоб побачити повні умови, приклад розрахунку та реквізити.</p>
  </div></div>
  <div class="article-wrap"><article class="article">
    <h2>Усі МФО каталогу</h2>
    <div class="table-wrap"><table class="mfo-table"><thead><tr><th>МФО</th><th>Сума</th><th>Строк</th><th>Ставка на день</th><th>Кредитор</th></tr></thead><tbody>{rows}</tbody></table></div>
    <p>Дані з фіду партнерської мережі станом на {esc(generated[:10])}. Кілька брендів можуть належати одній юридичній особі — про це в матеріалі <a href="/reytynhy/skilky-mfo-v-ukrayini-brendy-i-yurydychni-osoby/">хто стоїть за брендами МФО</a>.</p>
  </article></div>'''
    return page('/mfo/', 'Каталог МФО: умови, ставки та кредитор кожного бренду | TREBA CASH',
                f'Каталог {len(offers)} МФО: максимальна сума, строк, денна ставка та юридична особа кредитора. Повні умови й реквізити кожної компанії.',
                f'Усі МФО каталогу TREBA CASH: умови та кредитори', 'Таблиця оновлюється щодня з даних партнерської мережі.',
                [('Головна', '/'), ('Усі МФО', None)], body, label='Каталог', robots='noindex, follow')


def requisites_page(offers, generated):
    cards = []
    for o in sorted(offers, key=lambda x: x['name'].lower()):
        rows = [('Юридична особа', o.get('legal')), ('ЄДРПОУ', o.get('edrpou')), ('Адреса', o.get('address')),
                ('Телефон', o.get('phone')), ('Email', o.get('email'))]
        cards.append(f'<h3 id="{o["slug"]}"><a href="/mfo/{o["slug"]}/">{esc(o["name"])}</a></h3><table class="kv">'
                     + ''.join(f'<tr><th>{k}</th><td>{esc(v)}</td></tr>' for k, v in rows if v) + '</table>')
    body = f'''  <div class="article-wrap"><article class="article">
    <p>Юридичні дані всіх МФО, представлених на TREBA CASH, — для самостійної перевірки перед оформленням кредиту. Статус фінансової установи перевіряй у <a href="https://kis.bank.gov.ua/" target="_blank" rel="noopener">Державному реєстрі фінансових установ НБУ</a> за кодом ЄДРПОУ. Дані станом на {esc(generated[:10])}.</p>
    {''.join(cards)}
  </article></div>'''
    return page('/rekvizyty-partneriv/', 'Реквізити МФО-партнерів: юрособи, ЄДРПОУ, адреси | TREBA CASH',
                'Юридичні особи, коди ЄДРПОУ, адреси та контакти всіх МФО-партнерів TREBA CASH для перевірки в реєстрі НБУ.',
                'Реквізити МФО-партнерів TREBA CASH', 'Юридичні особи, ЄДРПОУ та контакти кредиторів.',
                [('Головна', '/'), ('Реквізити партнерів', None)], body, label='Прозорість')


# ------------------------------------------------------------------ SEO-вітрина (окремо від рекламної /porivnyannya-mfo/)
VITRINE_PATH = '/kredyt-onlayn/'


def vitrine_card(o, pos):
    promo = str(o.get('hasZeroBadge')).lower() == 'true'
    return (f'<div class="offer-card v-card" data-sum="{o["sum"]}" data-term="{o["term"]}" data-promo="{1 if promo else 0}" '
            f'data-rate="{o["dmin"]}" data-pos="{pos}">'
            f'<div class="offer-logo-wrap"><img src="{esc(o["logo"])}" alt="{esc(o["name"])}" loading="lazy" width="120" height="48" onerror="this.style.display=\'none\'"></div>'
            f'<div class="offer-badge">{esc(badge(o))}</div>'
            f'<div class="offer-stats"><div class="row">Макс. сума <b>до {fmt(o["sum"])} ₴</b></div>'
            f'<div class="row">На строк <b>до {o["term"]} дн.</b></div>'
            f'<div class="row">Ставка від <b>{pct(o["dmin"])}% / день</b></div></div>'
            f'<a class="offer-btn" href="#" data-go="{esc(o["ref"])}" data-offer="{esc(o["name"])}" data-pos="{pos}" target="_blank" rel="sponsored nofollow noopener noreferrer">Отримати гроші</a>'
            f'<a class="offer-info" href="/mfo/{o["slug"]}/">Умови {esc(o["name"])}</a></div>')


VITRINE_JS = r'''<script>
(function(){
  var grid=document.getElementById('offers-grid'); if(!grid) return;
  var cards=[].slice.call(grid.querySelectorAll('.v-card'));
  var state={term:0, sort:'pos'};
  var sum=document.getElementById('f-sum'), promo=document.getElementById('f-promo');
  var out=document.getElementById('f-count'), sumOut=document.getElementById('f-sum-out');
  function fmt(n){return new Intl.NumberFormat('uk-UA').format(Math.round(n));}
  function pct(r){var v=((r.value-r.min)/(r.max-r.min))*100; r.style.setProperty('--pct',v+'%');}
  function apply(){
    var s=+sum.value, n=0; pct(sum); sumOut.textContent=fmt(s)+' ₴';
    cards.sort(function(a,b){
      if(state.sort==='sum') return b.dataset.sum-a.dataset.sum;
      if(state.sort==='term') return b.dataset.term-a.dataset.term;
      if(state.sort==='rate') return a.dataset.rate-b.dataset.rate;
      return a.dataset.pos-b.dataset.pos;
    }).forEach(function(c){
      var ok=(+c.dataset.sum>=s)&&(+c.dataset.term>=state.term)&&(!promo.checked||c.dataset.promo==='1');
      c.style.display=ok?'':'none'; if(ok) n++; grid.appendChild(c);
    });
    out.textContent=n;
    try{(window.dataLayer=window.dataLayer||[]).push({event:'seo_vitrine_filter',sum:s,term:state.term,promo:promo.checked,sort:state.sort,results:n});}catch(e){}
  }
  function group(attr){
    [].forEach.call(document.querySelectorAll('[data-'+attr+']'),function(btn){
      btn.addEventListener('click',function(){
        [].forEach.call(document.querySelectorAll('[data-'+attr+']'),function(b){b.classList.remove('active');b.setAttribute('aria-pressed','false');});
        btn.classList.add('active'); btn.setAttribute('aria-pressed','true');
        state[attr]=attr==='term'?+btn.dataset[attr]:btn.dataset[attr]; apply();
      });
    });
  }
  group('term'); group('sort');
  sum.addEventListener('input',apply); promo.addEventListener('change',apply); apply();
  var ca=document.getElementById('c-sum'), cd=document.getElementById('c-days');
  function calc(){
    var a=+ca.value||0, d=+cd.value||0; pct(ca); pct(cd);
    document.getElementById('c-sum-out').textContent=fmt(a)+' ₴';
    document.getElementById('c-days-out').textContent=d+' дн.';
    document.getElementById('c-promo').textContent=fmt(a+a*0.0001*d)+' ₴';
    document.getElementById('c-max').textContent=fmt(a+a*0.01*d)+' ₴';
    document.getElementById('c-max-int').textContent=fmt(a*0.01*d)+' ₴';
    var m=0; cards.forEach(function(c){ if(+c.dataset.sum>=a && +c.dataset.term>=d) m++; });
    document.getElementById('c-match').textContent=m;
  }
  ca.addEventListener('input',calc); cd.addEventListener('input',calc); calc();
})();
</script>'''

# Стиль — як на рекламній вітрині /porivnyannya-mfo/: Unbounded для заголовків і чисел,
# скляна картка калькулятора, слайдери з білою кнопкою, фільтри-«пігулки» замість випадаючих списків.
VITRINE_CSS = '''<style>
.hero h1{font-family:'Unbounded',sans-serif;font-weight:900;letter-spacing:-0.03em;line-height:1.08}
.offers-title,.article h2,.v-section-title{font-family:'Unbounded',sans-serif;font-weight:900;letter-spacing:-.02em}
.calc-card{position:relative;background:rgba(255,255,255,.88);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);border:1px solid rgba(255,255,255,.7);border-radius:32px;padding:36px 40px 40px;box-shadow:0 30px 80px rgba(13,21,18,.12),0 10px 30px rgba(39,174,96,.1);margin:0 0 26px}
.calc-card::before{content:'';position:absolute;inset:0;border-radius:32px;padding:1px;background:linear-gradient(135deg,rgba(46,204,113,.5),rgba(245,185,66,.3),transparent);-webkit-mask:linear-gradient(#fff 0 0) content-box,linear-gradient(#fff 0 0);-webkit-mask-composite:xor;mask-composite:exclude;pointer-events:none}
.calc-title{display:flex;align-items:center;gap:10px;font-family:'Unbounded',sans-serif;font-size:20px;font-weight:900;color:#1a2421;margin:0 0 6px}
.calc-sub{font-size:14px;color:#5a6b64;margin:0 0 26px}
.calc-grid{display:grid;grid-template-columns:1fr 1fr;gap:28px;align-items:end}
.calc-field label{display:flex;justify-content:space-between;align-items:baseline;font-size:13px;font-weight:800;color:#1a2421;margin-bottom:12px}
.calc-field label .val{color:#1e8449;font-family:'Unbounded',sans-serif;font-size:15px}
.calc-card input[type=range]{-webkit-appearance:none;appearance:none;width:100%;height:8px;border-radius:99px;background:linear-gradient(90deg,#27ae60 0%,#27ae60 var(--pct,50%),#e3ece6 var(--pct,50%),#e3ece6 100%);outline:none;cursor:pointer;margin:6px 0}
.calc-card input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:26px;height:26px;border-radius:50%;background:#fff;border:4px solid #27ae60;box-shadow:0 4px 14px rgba(39,174,96,.4);cursor:grab;transition:transform .15s}
.calc-card input[type=range]::-webkit-slider-thumb:hover{transform:scale(1.15)}
.calc-card input[type=range]::-moz-range-thumb{width:26px;height:26px;border-radius:50%;background:#fff;border:4px solid #27ae60;box-shadow:0 4px 14px rgba(39,174,96,.4);cursor:grab}
.calc-results{margin-top:28px;padding-top:26px;border-top:1px dashed rgba(39,174,96,.25);display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
.calc-result{text-align:center;padding:14px 10px;border-radius:16px;background:rgba(39,174,96,.06)}
.calc-result b{display:block;font-family:'Unbounded',sans-serif;font-size:clamp(16px,2vw,22px);font-weight:900;color:#1e8449}
.calc-result span{display:block;margin-top:6px;font-size:11.5px;line-height:1.35;color:#5a6b64;font-weight:700}
.calc-result.gold b{color:#f5b942}
.calc-hint{font-size:12px;color:#5a6b64;margin-top:14px;text-align:center}
.filter-row{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 12px}
.filter-label{font-size:13px;font-weight:800;color:#5a6b64;margin-right:6px}
.sort-btn{display:inline-flex;align-items:center;gap:6px;padding:9px 18px;border-radius:999px;border:2px solid rgba(39,174,96,.2);background:#fff;color:#5a6b64;font:700 13px 'Manrope',sans-serif;cursor:pointer;transition:.2s}
.sort-btn:hover{border-color:#27ae60;color:#27ae60}
.sort-btn.active{background:linear-gradient(90deg,#27ae60,#2ecc71);color:#fff;border-color:transparent;box-shadow:0 4px 14px rgba(39,174,96,.3)}
.promo-filter-label{display:inline-flex;align-items:center;gap:10px;padding:9px 18px 9px 14px;border-radius:999px;border:2px solid rgba(245,185,66,.4);background:linear-gradient(120deg,rgba(245,185,66,.1),rgba(255,207,110,.06));cursor:pointer;font-size:13px;font-weight:800;color:#8a6100}
.promo-filter-label:hover{border-color:#f5b942;background:rgba(245,185,66,.15)}
.promo-filter-label input[type=checkbox]{appearance:none;-webkit-appearance:none;width:20px;height:20px;border-radius:6px;border:2px solid rgba(245,185,66,.6);background:#fff;cursor:pointer;position:relative;flex-shrink:0;margin:0}
.promo-filter-label input[type=checkbox]:checked{background:linear-gradient(120deg,#f5b942,#ffcf6e);border-color:#f5b942}
.promo-filter-label input[type=checkbox]:checked::after{content:'✓';position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#5c3d00;font-size:13px;font-weight:900}
.v-count{font-size:14px;margin:4px 0 16px;color:#5a6b64}.v-count b{font-family:'Unbounded',sans-serif;color:#1e8449}
.v-filters{margin:0 0 8px}
@media(max-width:860px){.calc-card{padding:26px 20px 28px;border-radius:24px}.calc-grid{grid-template-columns:1fr;gap:18px}.calc-results{grid-template-columns:repeat(2,1fr)}
.filter-row{display:grid;grid-template-columns:1fr 1fr;gap:8px}.filter-row .filter-label,.filter-row .promo-filter-label{grid-column:1/-1}.filter-row .sort-btn{justify-content:center;padding:9px 8px;font-size:12px}}
</style>'''


def vitrine_page(offers, generated):
    cards = '\n        '.join(vitrine_card(o, i + 1) for i, o in enumerate(offers))
    promo_n = sum(1 for o in offers if str(o.get('hasZeroBadge')).lower() == 'true')
    max_sum = max(o['sum'] for o in offers)
    max_term = max(o['term'] for o in offers)
    rows = ''.join(f'<tr><td>{esc(o["name"])}</td><td>до {fmt(o["sum"])} ₴</td><td>до {o["term"]} дн.</td>'
                   f'<td>від {pct(o["dmin"])}%</td><td>{"так" if str(o.get("hasZeroBadge")).lower() == "true" else "—"}</td>'
                   f'<td>{esc(o.get("legal") or "—")}</td></tr>' for o in offers)
    facts = ('<section class="law-facts"><h2>Що каже закон</h2><ul>'
             '<li><strong>Денна ставка — не більше 1%.</strong> Таке обмеження діє з 20.08.2024 за Законом №3498-IX. Якщо бачиш вищу ставку — це застарілі дані або порушення.</li>'
             '<li><strong>Жодних платежів поза договором.</strong> Кредитор не може вимагати платежі, яких немає в договорі чи в розрахунку денної ставки.</li>'
             '<li><strong>14 днів, щоб відмовитися.</strong> Стаття 15 закону про споживче кредитування дозволяє відмовитися від договору протягом 14 календарних днів без пояснення причин.</li>'
             '<li><strong>Ліцензія — у реєстрі НБУ.</strong> Перевіряй кредитора за кодом ЄДРПОУ в Державному реєстрі фінансових установ.</li></ul>'
             '<p class="law-src"><strong>Джерела:</strong> <a href="https://zakon.rada.gov.ua/laws/show/3498-20" target="_blank" rel="noopener">Закон №3498-IX</a>; '
             '<a href="https://zakon.rada.gov.ua/laws/show/1734-19" target="_blank" rel="noopener">Закон «Про споживче кредитування»</a>; '
             '<a href="https://kis.bank.gov.ua/" target="_blank" rel="noopener">Реєстр НБУ</a>.</p></section>')
    body = f'''  <div class="container">
    <div class="intro-wide">
      <p class="lead">{len(offers)} пропозицій МФО в одному місці: до {fmt(max_sum)} ₴ на строк до {max_term} днів, {promo_n} компаній дають першу позику під акційну ставку. Відфільтруй за сумою і строком, порівняй вартість у калькуляторі та подай заявку в 2–3 МФО — так шанс на схвалення вищий.</p>
    </div>
    <section class="calc-card" aria-labelledby="calc-title">
      <h2 class="calc-title" id="calc-title"><span aria-hidden="true">🧮</span> Калькулятор вартості кредиту</h2>
      <p class="calc-sub">Обери суму та строк — побачиш, скільки повернути, і скільки МФО дають такі умови.</p>
      <div class="calc-grid">
        <div class="calc-field"><label for="c-sum">Сума кредиту <span class="val" id="c-sum-out"></span></label><input id="c-sum" type="range" min="500" max="{max_sum}" step="500" value="5000"></div>
        <div class="calc-field"><label for="c-days">Строк <span class="val" id="c-days-out"></span></label><input id="c-days" type="range" min="1" max="60" step="1" value="30"></div>
      </div>
      <div class="calc-results" aria-live="polite">
        <div class="calc-result"><b id="c-promo"></b><span>до повернення за акцією 0,01%/день</span></div>
        <div class="calc-result"><b id="c-max"></b><span>до повернення за 1%/день (максимум за законом)</span></div>
        <div class="calc-result"><b id="c-max-int"></b><span>відсотки за 1%/день</span></div>
        <div class="calc-result gold"><b id="c-match"></b><span>МФО з такою сумою і строком</span></div>
      </div>
      <p class="calc-hint">Розрахунок орієнтовний: сума × денна ставка × дні. Точні умови — у паспорті споживчого кредиту.</p>
    </section>
    <section class="offers-section">
      <h2 class="offers-title">Підбір кредиту онлайн</h2>
      <p class="offers-sub">Дані оновлюються щодня автоматично · оновлено {esc(generated[:10])}</p>
      <div class="v-filters" role="group" aria-label="Фільтри">
        <div class="filter-row"><span class="filter-label">Сума від <b id="f-sum-out">1 000 ₴</b></span></div>
        <div class="calc-card" style="padding:18px 24px;margin:0 0 16px;border-radius:20px"><input id="f-sum" type="range" min="1000" max="{max_sum}" step="1000" value="1000" aria-label="Мінімальна сума"></div>
        <div class="filter-row"><span class="filter-label">Строк:</span>
          <button type="button" class="sort-btn active" data-term="0" aria-pressed="true">будь-який</button>
          <button type="button" class="sort-btn" data-term="30" aria-pressed="false">30+ днів</button>
          <button type="button" class="sort-btn" data-term="90" aria-pressed="false">90+ днів</button>
          <button type="button" class="sort-btn" data-term="180" aria-pressed="false">180+ днів</button>
          <button type="button" class="sort-btn" data-term="360" aria-pressed="false">рік</button></div>
        <div class="filter-row"><span class="filter-label">Сортувати:</span>
          <button type="button" class="sort-btn active" data-sort="pos" aria-pressed="true">рекомендовані</button>
          <button type="button" class="sort-btn" data-sort="rate" aria-pressed="false">мінімальна ставка</button>
          <button type="button" class="sort-btn" data-sort="sum" aria-pressed="false">більша сума</button>
          <button type="button" class="sort-btn" data-sort="term" aria-pressed="false">довший строк</button>
          <label class="promo-filter-label"><input id="f-promo" type="checkbox"> лише з акцією для нових клієнтів</label></div>
      </div>
      <p class="v-count">Знайдено пропозицій: <b id="f-count">{len(offers)}</b></p>
      <div class="offers-grid" id="offers-grid" data-ssr="1">
        {cards}
      </div>
    </section>
  </div>
  <div class="article-wrap"><article class="article">
    <h2>Як обрати кредит онлайн: 4 кроки</h2>
    <ol>
      <li><strong>Визнач суму і дату повернення.</strong> Бери рівно стільки, скільки потрібно, і строк — до дня, коли точно матимеш гроші.</li>
      <li><strong>Порівняй вартість у гривнях,</strong> а не відсоток на банері: калькулятор вище показує найкращий і найгірший законний сценарій.</li>
      <li><strong>Перевір кредитора в реєстрі НБУ</strong> за кодом ЄДРПОУ — реквізити всіх МФО є на сторінці <a href="/rekvizyty-partneriv/">реквізити партнерів</a>.</li>
      <li><strong>Подай 2–3 заявки, а не 10.</strong> У кожної МФО свій скоринг, але десятки запитів за день знижують шанси.</li>
    </ol>
    <h2>Порівняльна таблиця всіх МФО</h2>
    <div class="table-wrap"><table class="mfo-table"><thead><tr><th>МФО</th><th>Сума</th><th>Строк</th><th>Ставка на день</th><th>Акція</th><th>Кредитор</th></tr></thead><tbody>{rows}</tbody></table></div>
    <p>Денна ставка показана за даними партнерської мережі й не вище граничних 1% на день. Точні умови, реальну річну процентну ставку і графік дивись у паспорті споживчого кредиту до підписання. Як ми відбираємо пропозиції — у <a href="/reytynhy/metodolohiya-reytyngiv-treba-cash/">методології</a>.</p>
    {facts}
    <h2>Корисне перед заявкою</h2>
    <ul>
      <li><a href="/propozytsiyi/kredyt-onlayn-bez-vidmovy/">Кредит без відмови: що насправді означає «гарантоване схвалення»</a></li>
      <li><a href="/propozytsiyi/kredyt-z-poganoyu-ki/">Кредит з поганою кредитною історією</a></li>
      <li><a href="/propozytsiyi/skilky-koshtuye-kredyt-onlayn-vidsotky-mfo/">Скільки насправді коштує кредит онлайн</a></li>
      <li><a href="/blog/how-to-get-out-of-mfo-debt-trap/">Як вийти з боргів за мікрокредитами</a></li>
    </ul>
  </article></div>'''
    faqs = [('Де взяти кредит онлайн на картку?', f'У будь-якій із {len(offers)} МФО в переліку: заявка займає кілька хвилин, гроші надходять на картку після схвалення. Обирай за сумою, строком і вартістю, а кредитора перевіряй у реєстрі НБУ.'),
            ('Яка максимальна ставка за мікрокредитом?', 'З 20.08.2024 денна процентна ставка за споживчим кредитом не може перевищувати 1% (Закон №3498-IX). Для нових клієнтів багато МФО дають першу позику під 0,01% на день.'),
            ('Чи можна отримати кредит онлайн без відмови?', 'Гарантованого схвалення не дає жодна легальна МФО: кожна оцінює платоспроможність. Шанси підвищують правильні дані в анкеті, реалістична сума і 2–3 заявки в різні компанії.'),
            ('Чи можна відмовитися від кредиту після оформлення?', 'Так, протягом 14 календарних днів від укладення договору — письмово повідомивши кредитора й повернувши кошти з відсотками за фактичні дні користування.'),
            ('Чи бере TREBA CASH плату за підбір?', 'Ні. Сервіс безкоштовний для користувачів; ми отримуємо винагороду від партнерів за звернення через наші посилання.')]
    out = page(VITRINE_PATH, f'Кредит онлайн на картку: усі МФО України {TODAY.year} | TREBA CASH',
               f'Порівняння {len(offers)} МФО: кредит онлайн на картку до {fmt(max_sum)} ₴, фільтри за сумою і строком, калькулятор вартості та ставки в межах закону. Оновлюється щодня.',
               'Кредит онлайн на картку: порівняння всіх МФО', 'Фільтри, калькулятор і таблиця умов — дані оновлюються щодня.',
               [('Головна', '/'), ('Кредит онлайн', None)], body, faqs, label='Порівняння')
    return out.replace('</head>', VITRINE_CSS + '\n</head>', 1).replace('</body>', VITRINE_JS + '\n</body>', 1)


# ------------------------------------------------------------------ sitemap
def is_indexable(path, s):
    if 'http-equiv="refresh"' in s:
        return False
    m = re.search(r'<meta name="robots" content="([^"]*)"', s)
    if m and 'noindex' in m.group(1):
        return False
    c = re.search(r'<link rel="canonical" href="([^"]+)"', s)
    return not c or c.group(1) == SITE + path


def build_sitemap(state):
    try:
        old = dict(re.findall(r'<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>', rd('sitemap.xml')))
    except FileNotFoundError:
        old = {}
    urls = []
    for dp, dn, fn in os.walk(ROOT):
        if '.git' in dp or 'node_modules' in dp:
            continue
        if 'index.html' not in fn:
            continue
        rel = os.path.relpath(os.path.join(dp, 'index.html'), ROOT).replace(os.sep, '/')
        path = '/' + rel[:-len('index.html')]
        if path == '/./':
            path = '/'
        s = rd(rel)
        # KZ/MX — окремі гео-лендинги, власник просив їх не чіпати; у sitemap їх не було й немає
        if path.startswith(('/porivnyannya-mfo-kz/', '/porivnyannya-mfo-mx/')) or not is_indexable(path, s):
            continue
        body = re.sub(r'<div class="offers-grid".*?</div>\s*<div class="offers-more">', '', s, flags=re.S)  # ротація оферів ≠ оновлення
        h = hashlib.sha1(body.encode()).hexdigest()
        loc = SITE + path
        mod = re.search(r'article:modified_time" content="([\d-]+)"', s)
        if path not in state:            # перший запуск для сторінки: не вигадуємо дату
            lm = mod.group(1) if mod else old.get(loc, TODAY.isoformat())
        elif state[path] != h:           # вміст змінився
            lm = TODAY.isoformat()
        else:
            lm = old.get(loc, mod.group(1) if mod else TODAY.isoformat())
        state[path] = h
        prio = '1.0' if path == '/' else '0.9' if path.count('/') == 2 else '0.7'
        urls.append((path, lm, prio))
    urls.sort(key=lambda x: (x[0] != '/', x[0].count('/'), x[0]))
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p, lm, pr in urls:
        out.append(f'  <url>\n    <loc>{SITE}{p}</loc>\n    <lastmod>{lm}</lastmod>\n    <priority>{pr}</priority>\n  </url>')
    out.append('</urlset>\n')
    wr('sitemap.xml', '\n'.join(out))
    return len(urls)


# ------------------------------------------------------------------ main
def main():
    generated, offers = load_offers()
    if not offers:
        print('Фід порожній — збірку пропущено'); return 1
    changed = 0
    # 1. генеровані сторінки
    live = set()
    for o in offers:
        live.add(o['slug'])
        changed += wr(f'mfo/{o["slug"]}/index.html', mfo_page(o, offers, generated))
    changed += wr('mfo/index.html', mfo_index(offers, generated))
    changed += wr('kredyt-onlayn/index.html', vitrine_page(offers, generated))
    changed += wr('rekvizyty-partneriv/index.html', requisites_page(offers, generated))
    # МФО, що зникли з фіду → редирект на каталог
    if os.path.isdir(os.path.join(ROOT, 'mfo')):
        for d in os.listdir(os.path.join(ROOT, 'mfo')):
            if os.path.isdir(os.path.join(ROOT, 'mfo', d)) and d not in live:
                changed += wr(f'mfo/{d}/index.html', f'<!DOCTYPE html><html lang="uk"><head><meta charset="UTF-8"><title>МФО більше немає в каталозі | TREBA CASH</title>'
                              f'<link rel="canonical" href="{SITE}/mfo/"><meta http-equiv="refresh" content="0; url=/mfo/">'
                              f'<script>location.replace("/mfo/"+location.search)</script></head><body><a href="/mfo/">Усі МФО</a></body></html>\n')
    # 2. існуючі сторінки
    for dp, dn, fn in os.walk(ROOT):
        if '.git' in dp or 'index.html' not in fn:
            continue
        rel = os.path.relpath(os.path.join(dp, 'index.html'), ROOT).replace(os.sep, '/')
        path = '' if rel == 'index.html' else rel[:-len('index.html')]
        if path.startswith(PROTECTED) or path.startswith(('mfo/', 'rekvizyty-partneriv/', 'kredyt-onlayn/')):
            continue
        s = rd(rel)
        if 'http-equiv="refresh"' in s:
            continue
        n = ssr_page(path, s, offers)
        n = bump_year(n)
        n = premium(n)
        changed += wr(rel, n)
    # 3. sitemap
    state = {}
    if os.path.exists(STATE_FILE):
        state = json.loads(rd(os.path.relpath(STATE_FILE, ROOT)))
    count = build_sitemap(state)
    wr(os.path.relpath(STATE_FILE, ROOT), json.dumps(state, ensure_ascii=False, indent=0, sort_keys=True) + '\n')
    print(f'Оферів: {len(offers)}; змінено файлів: {changed}; URL у sitemap: {count}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
