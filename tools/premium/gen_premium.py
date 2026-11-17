"""Генерує assets/css/premium.css і assets/js/premium.js з шаблонів (візерунок іконок кодується в data-URI).
Запуск: python3 tools/premium/gen_premium.py"""
import urllib.parse, sys, os
R = sys.argv[1] if len(sys.argv) > 1 else os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
I = {
 'coin': '<circle cx="12" cy="12" r="9"/><path d="M9 10h6M9 13.2h6"/><path d="M14.6 8.2c-1.6-1.2-5-.7-5 1.5M9.4 15.8c1.6 1.2 5 .7 5-1.5"/>',
 'wallet': '<rect x="3" y="6" width="18" height="13" rx="2.5"/><path d="M3 9.5h15.5a2.5 2.5 0 0 1 2.5 2.5"/><path d="M16 12.5h5v3.5h-5a1.75 1.75 0 0 1 0-3.5z"/>',
 'card': '<rect x="2.5" y="5.5" width="19" height="13" rx="2.2"/><path d="M2.5 9.5h19M6 15h4"/>',
 'stack': '<ellipse cx="12" cy="6" rx="7" ry="2.5"/><path d="M5 6v4c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V6M5 10v4c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-4M5 14v4c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-4"/>',
 'note': '<rect x="2" y="7" width="20" height="10" rx="1.6"/><circle cx="12" cy="12" r="2.6"/><path d="M5.5 10v4M18.5 10v4"/>',
 'percent': '<path d="M18.5 5.5l-13 13"/><circle cx="7" cy="7" r="2.3"/><circle cx="17" cy="17" r="2.3"/>',
 'shield': '<path d="M12 3l7 3v5.2c0 4.4-3 7.9-7 9.8-4-1.9-7-5.4-7-9.8V6z"/><path d="M9 12l2.2 2.2L15.5 10"/>',
 'chart': '<path d="M4 4v16h16"/><path d="M7.5 15l4-4.5 3 3L20 7"/><path d="M16 7h4v4"/>',
 'calc': '<rect x="5" y="3" width="14" height="18" rx="2.2"/><path d="M8 7h8M8.5 11h.01M12 11h.01M15.5 11h.01M8.5 14.5h.01M12 14.5h.01M15.5 14.5h.01M8.5 18h.01M12 18h.01M15.5 18h.01"/>',
}
def g(name, x, y, s, rot=0):
    return f'<g transform="translate({x} {y}) rotate({rot} {12*s/24} {12*s/24}) scale({s/24})">{I[name]}</g>'
tile = ('<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320" viewBox="0 0 320 320" fill="none" stroke="#1f8a4c" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" opacity=".065">'
        + g('coin', 24, 30, 30, -8) + g('card', 150, 18, 34, 10) + g('wallet', 250, 86, 32, -6) + g('stack', 70, 140, 30, 4)
        + g('note', 186, 168, 36, -12) + g('percent', 22, 238, 24, 0) + g('calc', 120, 250, 28, 8) + g('chart', 262, 236, 28, -4) + '</svg>')
uri = "data:image/svg+xml," + urllib.parse.quote(tile, safe='')
css = open(os.path.join(os.path.dirname(__file__), 'premium.tpl.css'), encoding='utf-8').read().replace('__PATTERN__', uri)
open(os.path.join(R, 'assets/css/premium.css'), 'w', encoding='utf-8').write(css)
js = open(os.path.join(os.path.dirname(__file__), 'premium.tpl.js'), encoding='utf-8').read()
js = js.replace('__ICONS__', '{' + ','.join(f"{k}:'{v}'" for k, v in I.items()) + '}')
open(os.path.join(R, 'assets/js/premium.js'), 'w', encoding='utf-8').write(js)
print('ok', len(css), len(js))
