#!/usr/bin/env python3
"""
Скрипт для GitHub Actions: отримує актуальні офери МФО з PDL-Profit API
і генерує mfo-live-data.json для сторінки /porivnyannya-mfo/.

API_KEY береться з змінної середовища PDL_API_KEY (GitHub Secrets),
НІКОЛИ не хардкодиться в цьому файлі.
"""

import os
import sys
import json
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

API_KEY = os.environ.get("PDL_API_KEY")
if not API_KEY:
    print("❌ ПОМИЛКА: змінна середовища PDL_API_KEY не встановлена.")
    print("   Додай її в GitHub → Settings → Secrets and variables → Actions")
    sys.exit(1)

API_URL = f"https://pdl-profit.com/partnerapi/offers/data?api_key={API_KEY}&country=UA"

# ── Реквізити та дані, яких немає в API (юрособа, ЄДРПОУ, адреса) ──
# Підтягуються з окремого локального файлу requisites.json (не з API)
REQUISITES_FILE = "requisites.json"

# ── Наша статистика по оферах (для «розумного» топу на вітрині) ──
# Беремо ковзне вікно STATS_DAYS днів (API дозволяє до 70).
STATS_DAYS = 60
STATS_URL = "https://pdl-profit.com/partnerapi/statistic"


def fetch_offers():
    """Робить запит до PDL-Profit API і повертає список офферів (з урахуванням пагінації)."""
    all_offers = []
    page = 1
    max_pages = 1

    while page <= max_pages:
        url = f"{API_URL}&page={page}"
        req = urllib.request.Request(url, headers={"User-Agent": "TrebaCash-Bot/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.URLError as e:
            print(f"❌ Помилка запиту до API (сторінка {page}): {e}")
            sys.exit(1)

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            print(f"❌ Відповідь API не є коректним JSON (сторінка {page})")
            sys.exit(1)

        if payload.get("status") != "success":
            print(f"❌ API повернув помилку: {payload.get('message')}")
            sys.exit(1)

        page_offers = payload.get("data", [])
        all_offers.extend(page_offers)

        max_pages = payload.get("pages", 1)
        total_count = payload.get("count")
        print(f"   Сторінка {page}/{max_pages}: отримано {len(page_offers)} офферів (total count у відповіді: {total_count})")
        page += 1

    return all_offers


def _num(val):
    try:
        return float(str(val).replace(",", ".").replace(" ", ""))
    except (TypeError, ValueError):
        return 0.0


def _item_offer_key(item):
    """Повертає (id, name) оферу з рядка статистики tab=offer.
    Формат рядка в документації PDL не описаний, тому шукаємо кілька варіантів."""
    off = item.get("offer")
    oid, name = None, None
    if isinstance(off, dict):
        oid = off.get("id") or off.get("offer_id")
        name = off.get("name") or off.get("title")
    elif off is not None:
        name = str(off)
    oid = oid or item.get("offer_id") or item.get("id")
    name = name or item.get("offer_name") or item.get("name") or item.get("title")
    if name and not oid:
        m = re.search(r"\((\d+)\)", str(name))
        if m:
            oid = m.group(1)
    try:
        oid = int(oid) if oid is not None else None
    except (TypeError, ValueError):
        oid = None
    return oid, clean_name(str(name)) if name else None


def fetch_own_stats():
    """Наша статистика по оферах за останні STATS_DAYS днів:
    {id або назва: {"uniqs", "approved", "payout"}}. Якщо API недоступний —
    повертає {} і сайт сортує як раніше (помилка тут не зупиняє оновлення оферів)."""
    to_d = datetime.now(timezone.utc).date()
    from_d = to_d - timedelta(days=STATS_DAYS)
    stats, page, pages = {}, 1, 1
    try:
        while page <= pages and page <= 20:
            url = (f"{STATS_URL}?api_key={API_KEY}&tab=offer&from={from_d}&to={to_d}"
                   f"&country=UA&pp=100&page={page}")
            req = urllib.request.Request(url, headers={"User-Agent": "TrebaCash-Bot/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            if payload.get("status") != "success":
                print(f"⚠️ Statistic API: {payload.get('message')}")
                return {}
            data = payload.get("data") or {}
            items = data.get("items") if isinstance(data, dict) else data
            items = items or []
            if page == 1 and items:
                print(f"   Statistic API: поля рядка {sorted(items[0].keys())}")
            for it in items:
                oid, name = _item_offer_key(it)
                if oid is None and not name:
                    continue
                row = {
                    "uniqs": int(_num(it.get("uniqs"))),
                    "approved": int(_num(it.get("approved"))),
                    "payout": round(_num(it.get("payout")), 2),
                }
                for key in (oid, name):
                    if key is None:
                        continue
                    prev = stats.get(key)
                    if prev:
                        for f in row:
                            prev[f] += row[f]
                    else:
                        stats[key] = dict(row)
            pages = int(_num(payload.get("pages") or (data.get("pages") if isinstance(data, dict) else 1) or 1))
            page += 1
    except Exception as e:  # мережа, JSON, формат — не валимо весь крок
        print(f"⚠️ Не вдалося отримати статистику по оферах: {e}")
        return {}
    print(f"📊 Статистика по оферах за {STATS_DAYS} днів: {len([k for k in stats if isinstance(k, int)])} оферів з ID")
    return stats


def load_requisites():
    """Завантажує локальний файл з реквізитами (ЄДРПОУ, адреса тощо)."""
    if not os.path.exists(REQUISITES_FILE):
        print(f"⚠️  Файл {REQUISITES_FILE} не знайдено — реквізити не будуть додані.")
        return {}
    with open(REQUISITES_FILE, encoding="utf-8") as f:
        return json.load(f)


def clean_name(name):
    """Прибирає зайві суфікси типу ' UA' з назви оферу."""
    return re.sub(r"\s+UA$", "", name).strip()


def to_float(val, default=0.0):
    try:
        return float(str(val).replace(",", "."))
    except (ValueError, TypeError):
        return default


def to_int(val, default=0):
    try:
        return int(float(str(val).replace(",", ".")))
    except (ValueError, TypeError):
        return default


def determine_badge(sum_val, term_val):
    """Логіка кольорового бейджа за сумою/строком (та сама, що на сайті)."""
    if sum_val >= 50000:
        return (f"До {int(sum_val/1000)} 000 ₴ на картку", "blue")
    if term_val >= 200:
        return ("До 12 місяців на повернення", "purple")
    if term_val <= 20:
        return ("Швидке рішення за хвилини", "teal")
    return ("Вигідні умови для нових клієнтів", "green")


# Ручні золоті бейджі (назва -> текст), щоб щоденне оновлення їх не скидало
FORCED_GOLD_BADGE = {"FreshCash": "Перша позика під 0.1%*"}


def transform_offer(offer, requisites):
    """Конвертує один офер з формату API у формат нашого сайту."""
    name = clean_name(offer.get("name", ""))

    first_credit_sum = to_int(offer.get("first_credit") or offer.get("credit"), 0)
    term = to_int(offer.get("term") or offer.get("days"), 30)

    first_pct = to_float(offer.get("first_credit_percent"), None)
    standard_pct = to_float(offer.get("first_credit_percent_standard"), None)

    # РРПС orієнтовно: денна ставка * 365 (спрощено, для відображення діапазону)
    rate_min = round(first_pct * 365, 1) if first_pct is not None else None
    rate_max = round(standard_pct * 365, 1) if standard_pct is not None else rate_min

    # Золотий бейдж — якщо ставка першого кредиту суттєво нижча за стандартну
    has_zero_badge = first_pct is not None and first_pct <= 0.5

    badge_text, badge_color = determine_badge(first_credit_sum, term)

    req = requisites.get(name, {})

    forced_gold = FORCED_GOLD_BADGE.get(name)
    if forced_gold:
        has_zero_badge = True

    return {
        "id": offer.get("id"),
        "name": name,
        "logo": offer.get("image"),  # пряме посилання з API, свій хостинг не потрібен
        "ref": offer.get("url"),
        "sum": first_credit_sum,
        "term": term,
        "rateMin": rate_min if rate_min is not None else 0,
        "rateMax": rate_max if rate_max is not None else 0,
        "badge": badge_text,
        "badgeColor": badge_color,
        "hasZeroBadge": has_zero_badge,
        "goldBadgeText": forced_gold or (
            f"Перша позика під {first_pct}%*" if has_zero_badge and first_pct is not None
            else "Перша позика під 0,01%*" if has_zero_badge else None
        ),
        "legal": req.get("legal"),
        "edrpou": req.get("edrpou"),
        "address": req.get("address"),
        "phone": req.get("phone"),
        "email": req.get("email"),
        # Мережеві показники PDL (усі вебмайстри) — апріорна оцінка для нових оферів
        "epcNet": to_float(offer.get("epc_general"), None),
        "crNet": to_float(offer.get("cr_general"), None),
    }


def main():
    print("📡 Запит до PDL-Profit API...")
    raw_offers = fetch_offers()
    print(f"✅ Отримано офферів: {len(raw_offers)}")

    requisites = load_requisites()
    print(f"📋 Завантажено реквізитів для {len(requisites)} компаній")

    transformed = [transform_offer(o, requisites) for o in raw_offers]

    own = fetch_own_stats()
    matched = 0
    for o in transformed:
        st = own.get(o.get("id")) or own.get(o.get("name"))
        if st:
            o["stats60"] = st
            matched += 1
    print(f"🔗 Статистику зіставлено з {matched} оферами")

    output = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "count": len(transformed),
        "statsDays": STATS_DAYS if own else None,
        "offers": transformed,
    }

    with open("mfo-live-data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"💾 Збережено mfo-live-data.json ({len(transformed)} офферів)")


if __name__ == "__main__":
    main()
