"""plan.json + points_gcj.json + tiles_meta.json -> <行程目录>/site/index.html（Artifact 页面，瓦片在 site/tiles/）。

    python3 build_page.py <行程目录>

plan.json 结构见 references/plan-schema.md。key_facts 的第一条如果以「出发前要办」「已买的票」开头，
会渲染成页面顶部的黄色待办框（用 ①②③ 分条）。
"""
import html, json, os, re, sys

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
trip = sys.argv[1]
plan = json.load(open(os.path.join(trip, 'plan.json')))
pts = json.load(open(os.path.join(trip, 'points_gcj.json')))
meta = json.load(open(os.path.join(trip, 'tiles_meta.json')))
E = lambda s: html.escape(str(s or ''))
PT = {p['id']: p for p in pts}
for p in pts:
    p['major'] = p['kind'] == 'station' and '地铁' not in p['name']

LIGHT = [('#b3392a', '#f7e3de'), ('#2b6a58', '#dcece6'), ('#3b5b9a', '#e1e7f4'), ('#7a3f8c', '#efe2f3'), ('#1f6f8b', '#dcedf3')]
DARK = [('#e57563', '#3a211c'), ('#5fb89c', '#1a302a'), ('#8aa6e0', '#1e2638'), ('#c592d6', '#2f2236'), ('#6ec3df', '#17303a')]
ndays = len(plan['days'])
day_ids = list(range(1, ndays + 1))
tok = lambda pal: ' '.join(f'--d{i}:{pal[(i - 1) % 5][0]}; --d{i}-soft:{pal[(i - 1) % 5][1]};' for i in day_ids)
day_rules = '\n'.join(f'.day{i}{{--dc:var(--d{i});--dcs:var(--d{i}-soft)}} .mk.d{i}{{background:var(--d{i})}} .tc{i}{{border-top-color:var(--d{i})}}' for i in day_ids)
def _label(i, d):
    m = re.match(r'\d{4}-(\d{2})-(\d{2})', d.get('date', ''))
    return f'{int(m.group(1))}/{int(m.group(2))}' if m else f'第{i}天'


day_label = {i: _label(i, d) for i, d in enumerate(plan['days'], 1)}


def amap_link(p):
    return f"https://uri.amap.com/marker?position={p['lon']:.6f},{p['lat']:.6f}&name={html.escape(p['name'])}&coordinate=gaode&callnative=1"


def seg_html(seg, di, si):
    ids = [i for i in (seg.get('map_ids') or []) if i in PT]
    o = [f'<li class="seg" id="d{di}s{si}"><div class="seg-time">{E(seg["time"])}</div><div class="seg-body">',
         f'<h4>{E(seg["title"])}</h4><p class="place">{E(seg["place"])}</p>',
         f'<p class="row"><span class="lab">怎么去</span><span>{E(seg["getting_there"])}</span></p>',
         f'<p class="row"><span class="lab">主线</span><span>{E(seg["do_what"])}</span></p>']
    if seg.get('booking') and seg['booking'].strip('。 ') not in ('无需预约', '不用预约', '无'):
        o.append(f'<p class="row"><span class="lab lab-book">预约</span><span>{E(seg["booking"])}</span></p>')
    if seg.get('tips'):
        o.append('<ul class="tips">' + ''.join(f'<li>{E(t)}</li>' for t in seg['tips']) + '</ul>')
    if seg.get('plan_b'):
        o.append('<div class="planb"><div class="planb-h">替代方案</div>' + ''.join(
            f'<div class="pb"><span class="pb-if">如果{E(b["trigger"].removeprefix("如果"))}</span><span class="pb-then">{E(b["alternative"])}</span></div>'
            for b in seg['plan_b']) + '</div>')
    links = []
    fa = next((f for f in plan['food_areas'] if f['id'] == seg.get('food_area_id')), None)
    if fa:
        links.append(f'<a class="chip" href="#food-{E(fa["id"])}">吃什么 · {len(fa["options"])} 家可选</a>')
    if ids:
        links.append(f'<button class="chip chip-map" data-fly="{E(",".join(ids))}">在地图上看</button>')
        links += [f'<a class="chip chip-nav" href="{E(amap_link(PT[i]))}" target="_blank" rel="noopener">高德导航 · {E(PT[i]["name"])}</a>' for i in ids[:3]]
    if links:
        o.append('<div class="seg-links">' + ''.join(links) + '</div>')
    o.append('</div></li>')
    return ''.join(o)


days_html = ''.join(f'''<section class="day day{di}" id="day{di}"><header class="day-h"><div class="day-num">DAY {di}</div><div>
  <h2>{E(d["date"])} {E(d.get("weekday", ""))} · {E(d["theme"])}</h2>{f'<p class="weather">{E(d["weather"])}</p>' if d.get("weather") else ''}</div></header>
  <ol class="timeline">{''.join(seg_html(s, di, si) for si, s in enumerate(d['segments']))}</ol></section>'''
                    for di, d in enumerate(plan['days'], 1))


def fo_html(o):
    br = f' <span class="fo-br">{E(o["branch"])}</span>' if o.get('branch') else ''
    pp = f'<span class="pp">人均 {E(o["price_pp"])}</span>' if o.get('price_pp') else ''
    q = f'<p class="fo-q"><b>排队</b> {E(o["queue"])}</p>' if o.get('queue') else ''
    c = f'<p class="fo-c"><b>注意</b> {E(o["caution"])}</p>' if (o.get('caution') or '').strip('—- ') else ''
    return f'<div class="fo"><div class="fo-name">{E(o["name"])}{br}</div><div class="fo-meta"><span class="must">必点 {E(o["must_order"])}</span>{pp}</div><p class="fo-why">{E(o["why"])}</p>{q}{c}</div>'


food_html = ''.join(f'<article class="fa" id="food-{E(f["id"])}"><header><span class="meal">{E(f["meal"])}</span><h3>{E(f["area"])}</h3></header><div class="fo-grid">{"".join(fo_html(o) for o in f["options"])}</div></article>'
                    for f in plan['food_areas'])
def must_html(m):
    when = f'<em>{E(m["when"])}</em>' if m.get('when') else ''
    return f'<li><b>{E(m["dish"])}</b><span>{E(m["where"])}</span>{when}</li>'


must = ''.join(must_html(m) for m in plan.get('must_eat', []))


def bk_html(b):
    rule = f'<p><b>规则</b> {E(b["rule"])}</p>' if b.get('rule') else ''
    now = f'<p class="now"><b>要做</b> {E(b["do_now"])}</p>' if b.get('do_now') else ''
    return f'<li><div class="bk-item">{E(b["item"])}</div><div class="bk-ch">{E(b["channel"])}</div>{rule}{now}<p><b>不行的话</b> {E(b["if_fail"])}</p></li>'


todo_html, rules = '', []
for f in plan['key_facts']:
    label, _, body = f.partition('：')
    if not todo_html and re.match(r'(出发前要办|已买的票|今天要办|\d+/\d+.*要办)', label):
        items = [x.strip('；;。 ') for x in re.split('[①②③④⑤⑥⑦⑧⑨⑩]', body) if x.strip('；;。 ')]
        todo_html = f'<div class="todo"><h3>{E(label)}</h3><ol>' + ''.join(f'<li>{E(x)}</li>' for x in items) + '</ol></div>'
    elif label in ('去程', '回程', '酒店', '住宿') and plan.get('trip_cards'):
        continue
    else:
        rules.append(f'<dt>{E(label)}</dt><dd>{E(body)}</dd>')
cards = ''.join(f'<div class="tc tc{c.get("day", 0)}"><b>{E(c["label"])}</b><strong>{E(c["big"])}</strong><span>{E(c["sub"])}</span></div>' for c in plan.get('trip_cards', []))
srcs = ''.join(f'<li><a href="{E(s["url"])}" target="_blank" rel="noopener">{E(s["title"])}</a></li>' if s.get('url') else f'<li>{E(s["title"])}</li>' for s in plan['sources'])
routes = {i: [x for x in (d.get('route') or []) if x in PT] for i, d in enumerate(plan['days'], 1)}
title_text = re.sub('<[^>]+>', '', plan['title'])
map_data = json.dumps({'points': pts, 'index': meta['index'], 'routes': routes, 'days': day_ids, 'dayLabels': day_label}, ensure_ascii=False)

page = open(os.path.join(SKILL, 'assets', 'template.html')).read()
rep = {
    '%%LEAFLET_CSS%%': open(os.path.join(SKILL, 'assets', 'leaflet.min.css')).read(),
    '%%DAY_TOKENS_LIGHT%%': tok(LIGHT), '%%DAY_TOKENS_DARK%%': tok(DARK), '%%DAY_RULES%%': day_rules,
    '%%TITLE_TEXT%%': E(title_text), '%%TITLE%%': plan['title'], '%%KICKER%%': E(plan.get('kicker', '')),
    '%%ONE_LINE%%': E(plan['one_line']), '%%TODO%%': todo_html, '%%TRIP_CARDS%%': cards,
    '%%NAV_DAYS%%': ''.join(f'<a href="#day{i}">{E(day_label[i])}</a>' for i in day_ids),
    '%%FILTER_DAYS%%': ''.join(f'<button class="fbtn" data-f="{i}" aria-pressed="false">{E(day_label[i])} 主线</button>' for i in day_ids),
    '%%LEGEND_DAYS%%': ''.join(f'<span><i style="background:var(--d{i})"></i>{E(day_label[i])} 主线</span>' for i in day_ids),
    '%%RULES%%': ''.join(rules), '%%DAYS%%': days_html, '%%FOOD%%': food_html, '%%MUST%%': must,
    '%%BOOKINGS%%': ''.join(bk_html(b) for b in plan['bookings']),
    '%%CONTS%%': ''.join(f'<li><b>{E(c["scenario"])}</b><span>{E(c["action"])}</span></li>' for c in plan['contingencies']),
    '%%BUDGET%%': ''.join(f'<tr><td>{E(b["item"])}</td><td>{E(b["cost"])}</td></tr>' for b in plan.get('budget', [])),
    '%%PACKING%%': ''.join(f'<li>{E(x)}</li>' for x in plan.get('packing', [])),
    '%%SOURCES%%': srcs, '%%MAP_DATA%%': map_data,
}
for k, v in rep.items():
    page = page.replace(k, v)
left = re.findall(r'%%[A-Z_]+%%', page)
if left:
    raise SystemExit(f'模板里还有没替换的占位符：{left}')
missing = sorted({i for r in (d.get('route') or [] for d in plan['days']) for i in r if i not in PT})
if missing:
    print('⚠️ route 里有找不到坐标的点（已跳过）：', missing)
os.makedirs(os.path.join(trip, 'site'), exist_ok=True)
open(os.path.join(trip, 'site', 'index.html'), 'w').write(page)
print('ok', os.path.join(trip, 'site', 'index.html'), f'{len(page) // 1024} KB')
