"""plan.json -> <行程目录>/offline/plan.md：给手机上的 Claude 当「随身助手资料」。

    python3 make_phone_md.py <行程目录> [返程硬约束一句话]

网页 HTML 里大部分是地图数据（几 MB），手机 Claude 读不了，所以单独出一份纯文本：
开头是给 Claude 的说明（先给结论、简短、不能误了返程车），后面是硬信息、流程、替代方案、每餐备选、预约和应急。
"""
import json, os, re, sys

trip = sys.argv[1]
hard = sys.argv[2] if len(sys.argv) > 2 else ''
p = json.load(open(os.path.join(trip, 'plan.json')))
T = lambda s: re.sub('<[^>]+>', '', str(s or ''))
L = [f"# {T(p['title'])}：随身助手资料", '',
     '## 给 Claude 的说明',
     '- 你是我这趟旅行的随身助手。我会在路上用**语音**问你，请**先给结论、回答简短**（3–5 句），需要时再展开。',
     '- 以下面的「流程」为准；有变动时从各段的「替代方案」「每餐备选」「应急」里挑最顺路的，告诉我**去哪、怎么走、要多久、用哪张票（哪个 App）**。',
     '- 我问「现在该干嘛」时，按我说的当前时间/地点对照流程回答。需要最新信息（营业时间、排队、天气、限流）时请联网搜索并说明来源。',
     '- 时间都是北京时间。']
if hard:
    L.append(f'- **硬约束**：{hard}')
L += ['', '## 硬信息与已买的票']
for c in p.get('trip_cards', []):
    L.append(f"- **{c['label']}**：{c['big']}，{c['sub']}")
for f in p['key_facts']:
    L.append(f'- {f}')
L += ['', '## 预约 / 票在哪个 App']
for b in p['bookings']:
    L.append(f"- **{b['item']}**（{b['channel']}）{('：' + b['rule']) if b.get('rule') else ''}；{b.get('do_now', '')}；不行的话：{b['if_fail']}")
for d in p['days']:
    L += ['', f"## {d['date']} {d.get('weekday', '')} · {d['theme']}"]
    if d.get('weather'):
        L.append(f"天气：{d['weather']}")
    for s in d['segments']:
        L.append(f"- **{s['time']} {s['title']}**（{s['place']}）")
        L.append(f"  - 怎么去：{s['getting_there']}")
        L.append(f"  - 做什么：{s['do_what']}")
        if s.get('booking') and s['booking'].strip('。 ') not in ('不用预约', '无需预约', '无'):
            L.append(f"  - 票/预约：{s['booking']}")
        for t in s.get('tips', []):
            L.append(f'  - 提示：{t}')
        for b in s.get('plan_b', []):
            L.append(f"  - 替代方案｜如果{b['trigger'].removeprefix('如果')} → {b['alternative']}")
L += ['', '## 每餐备选']
for f in p['food_areas']:
    opts = '；'.join(f"{o['name']}（{o.get('branch', '')}，必点 {o['must_order']}{('，人均 ' + o['price_pp']) if o.get('price_pp') else ''}{('，注意：' + o['caution']) if (o.get('caution') or '').strip('—- ') else ''}）" for o in f['options'])
    L.append(f"- **{f['meal']} · {f['area']}**：{opts}")
L += ['', '## 应急']
L += [f"- **{c['scenario']}**：{c['action']}" for c in p['contingencies']]
os.makedirs(os.path.join(trip, 'offline'), exist_ok=True)
out = os.path.join(trip, 'offline', 'plan.md')
open(out, 'w').write('\n'.join(L) + '\n')
print('ok', out, f'{os.path.getsize(out) // 1024} KB')
