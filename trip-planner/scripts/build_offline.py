"""把 site/index.html 打包成一个不联网也能看的单文件（发微信/存手机），外加一张静态路线总览图。

    <有 Pillow 的 python> build_offline.py <行程目录>

需要 Pillow。本机 python3 没有的话：
    python3 -m venv ~/.cache/trip-planner/venv && ~/.cache/trip-planner/venv/bin/pip install pillow
然后用 ~/.cache/trip-planner/venv/bin/python 跑本脚本。

做了这些事：
- 瓦片转 WebP（质量 75，文字几乎无损，体积约一半）后内嵌；Leaflet 内联，不依赖任何 CDN
- 去掉 Google Fonts（国内会卡住页面渲染）
- 画一张静态路线总览图（JPG），内嵌在页面里：浏览器能跑脚本时默认收起、可点开长按保存；
  微信/文件 App 的预览如果不跑脚本，交互地图自动隐藏，只显示静态图
输出：<行程目录>/offline/<标题>.html 和 <行程目录>/offline/路线总览.jpg
"""
import base64, io, json, math, os, re, sys, time, urllib.request
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit('缺 Pillow：python3 -m venv ~/.cache/trip-planner/venv && ~/.cache/trip-planner/venv/bin/pip install pillow，'
             '再用 ~/.cache/trip-planner/venv/bin/python 运行本脚本')

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
trip = sys.argv[1]
CACHE = os.path.expanduser('~/.cache/trip-planner')
page = open(os.path.join(trip, 'site', 'index.html')).read()
meta = json.load(open(os.path.join(trip, 'tiles_meta.json')))
plan = json.load(open(os.path.join(trip, 'plan.json')))
MAP = json.loads(re.search(r'const MAP = (\{.*?\});\n', page).group(1))
PTS = {p['id']: p for p in MAP['points']}
BG = (249, 247, 243)


def png(z, x, y):
    p = os.path.join(CACHE, 'amap', f'{z}_{x}_{y}.png')
    if not os.path.exists(p):
        u = f'https://webrd0{1 + (x + y) % 4}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}'
        for attempt in range(3):
            try:
                data = urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=15).read()
                if data[:4] == b'\x89PNG':
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                    open(p, 'wb').write(data)
                    break
            except Exception:
                time.sleep(1 + attempt)
    if not os.path.exists(p):
        return None
    im = Image.open(p).convert('RGBA')
    bg = Image.new('RGBA', im.size, BG + (255,))
    bg.alpha_composite(im)
    return bg.convert('RGB')


# 1. tiles -> webp base64
os.makedirs(os.path.join(CACHE, 'webp'), exist_ok=True)
tiles = {}
for key in meta['tiles']:
    z, xy = key.split('/')
    x, y = map(int, xy.split('_'))
    wp = os.path.join(CACHE, 'webp', f'{z}_{x}_{y}.webp')
    if not os.path.exists(wp):
        im = png(int(z), x, y)
        if im is None:
            continue
        im.save(wp, 'WEBP', quality=75, method=6)
    tiles[key] = base64.b64encode(open(wp, 'rb').read()).decode()
print('tiles', len(tiles), f'{sum(map(len, tiles.values())) / 1e6:.1f} MB(b64)')

# 2. static route map
LIGHT = [(179, 57, 42), (43, 106, 88), (59, 91, 154), (122, 63, 140), (31, 111, 139)]
used = [i for d in MAP['days'] for i in MAP['routes'].get(str(d), []) if i in PTS]
if not used:
    used = list(PTS)
for Z in (15, 14, 13, 12):
    W = 256 * 2 ** Z
    px = lambda lat, lon, W=W: ((lon + 180) / 360 * W, (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * W)
    xs, ys = zip(*[px(PTS[i]['lat'], PTS[i]['lon']) for i in used])
    if max(xs) - min(xs) < 1300 and max(ys) - min(ys) < 2000:
        break
PAD = 70
x0, y0, x1, y1 = int(min(xs)) - PAD, int(min(ys)) - PAD, int(max(xs)) + PAD, int(max(ys)) + PAD
if x1 - x0 < 700:
    c = (x0 + x1) // 2
    x0, x1 = c - 350, c + 350
canvas = Image.new('RGB', (x1 - x0, y1 - y0), BG)
for tx in range(x0 // 256, x1 // 256 + 1):
    for ty in range(y0 // 256, y1 // 256 + 1):
        t = png(Z, tx, ty)
        if t:
            canvas.paste(t, (tx * 256 - x0, ty * 256 - y0))
FONTS = ['/System/Library/Fonts/Hiragino Sans GB.ttc', '/System/Library/Fonts/STHeiti Medium.ttc', '/System/Library/Fonts/PingFang.ttc',
         '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', '/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc']
fp = next((f for f in FONTS if os.path.exists(f)), None)
font = (lambda size, bold=False: ImageFont.truetype(fp, size, index=1 if (bold and 'Hiragino' in fp) else 0)) if fp else (lambda size, bold=False: ImageFont.load_default())
loc = lambda i: (px(PTS[i]['lat'], PTS[i]['lon'])[0] - x0, px(PTS[i]['lat'], PTS[i]['lon'])[1] - y0)
ov = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
d = ImageDraw.Draw(ov)
for day in reversed(MAP['days']):
    seq = [loc(i) for i in MAP['routes'].get(str(day), []) if i in PTS]
    if len(seq) > 1:
        d.line(seq, fill=(255, 255, 255, 230), width=11, joint='curve')
        d.line(seq, fill=LIGHT[(day - 1) % 5] + (235,), width=6, joint='curve')
canvas = Image.alpha_composite(canvas.convert('RGBA'), ov)
d = ImageDraw.Draw(canvas)
num = {}
for day in MAP['days']:
    main = sorted([p for p in MAP['points'] if p['day'] == day and p['order'] > 0 and p['kind'] in ('sight', 'night')], key=lambda p: p['order'])
    for n, p in enumerate(main, 1):
        num[p['id']] = (day, n, p['name'])


def badge(xy, text, fill, square=False, r=16):
    x, y = xy
    box = [x - r, y - r, x + r, y + r]
    (d.rounded_rectangle(box, 6, fill=fill, outline='white', width=3) if square else d.ellipse(box, fill=fill, outline='white', width=3))
    d.text((x, y), text, font=font(17, True), fill='white', anchor='mm')


for pid, (day, n, _) in sorted(num.items(), key=lambda kv: (-kv[1][0], kv[1][1])):
    badge(loc(pid), str(n), LIGHT[(day - 1) % 5])
for p in MAP['points']:
    if p['kind'] == 'hotel':
        badge(loc(p['id']), '住', (35, 31, 27), square=True, r=18)
    elif p['kind'] == 'station' and p.get('major'):
        badge(loc(p['id']), '站', (35, 31, 27), square=True, r=18)
short = lambda s: re.split('[（(]', s)[0].strip()[:16]
cols = min(len(MAP['days']), 3)
rows_per = [sum(1 for v in num.values() if v[0] == day) for day in MAP['days']]
blocks = math.ceil(len(MAP['days']) / cols)
LH = 34
leg_h = sum(70 + max(rows_per[b * cols:(b + 1) * cols] or [0]) * LH for b in range(blocks)) + 50
out = Image.new('RGB', (canvas.width, canvas.height + leg_h), (255, 253, 248))
out.paste(canvas.convert('RGB'), (0, 0))
d = ImageDraw.Draw(out)
colw = canvas.width // cols
yb = canvas.height + 24
for b in range(blocks):
    days = MAP['days'][b * cols:(b + 1) * cols]
    for ci, day in enumerate(days):
        cx = 28 + ci * colw
        col = LIGHT[(day - 1) % 5]
        d.text((cx, yb), f"{MAP['dayLabels'][str(day)]} 主线", font=font(24, True), fill=col)
        for k, (n, name) in enumerate(sorted((n, nm) for pid, (dd, n, nm) in num.items() if dd == day)):
            yy = yb + 50 + k * LH
            d.ellipse([cx, yy - 13, cx + 26, yy + 13], fill=col)
            d.text((cx + 13, yy), str(n), font=font(17, True), fill='white', anchor='mm')
            d.text((cx + 38, yy), short(name), font=font(21), fill=(35, 31, 27), anchor='lm')
    yb += 70 + max(rows_per[b * cols:(b + 1) * cols] or [0]) * LH
d.text((28, out.height - 26), '■住 = 酒店　■站 = 火车站　连线只表示先后顺序　底图 © 高德地图', font=font(16), fill=(108, 100, 90), anchor='lm')
os.makedirs(os.path.join(trip, 'offline'), exist_ok=True)
jpg_p = os.path.join(trip, 'offline', '路线总览.jpg')
out.save(jpg_p, 'JPEG', quality=84, optimize=True, progressive=True)
static_b64 = base64.b64encode(open(jpg_p, 'rb').read()).decode()
print('static map', out.size, f'{os.path.getsize(jpg_p) // 1024} KB', f'z{Z}')

# 3. transform page
h = re.sub(r'<link rel="(preconnect|stylesheet)" href="https://fonts\.g[^>]*>\n', '', page)
h = ('<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8">\n'
     '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
     '<script>document.documentElement.classList.add("js")</script>\n') + h
h = h.replace('</style>', '''body{margin:0;-webkit-text-size-adjust:100%}
[hidden]{display:none!important}
img{max-width:100%}
html:not(.js) .map-card,html:not(.js) .map-note,html:not(.js) #static-toggle,html:not(.js) .chip-map{display:none}
.static-map{margin:12px 0 0;background:var(--surface);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.static-map img{display:block;width:100%;height:auto}
.static-map figcaption{font-size:12px;color:var(--muted);padding:8px 12px}
#static-toggle{margin-top:10px}
</style>''', 1)
assert '<p class="map-note">' in h
h = h.replace('<p class="map-note">', f'''<button class="chip" id="static-toggle" hidden>看静态总览图（可长按保存到相册）</button>
  <figure class="static-map" id="static-map"><img alt="路线总览图" src="data:image/jpeg;base64,{static_b64}"><figcaption>路线总览（静态图，可以长按保存）。不同颜色是不同的天，数字对应图下方的列表。</figcaption></figure>
  <p class="map-note">''', 1)
leaflet = open(os.path.join(SKILL, 'assets', 'leaflet.min.js')).read()
h = h.replace('<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>',
              '<script>' + leaflet + '</script>\n<script>window.TILES=' + json.dumps(tiles, separators=(',', ':')) + '</script>')
h, n = re.subn(r"const INDEX = \{\};.*?return imgs\[k\];\n  \}", '''const T = window.TILES || {};
  const imgs = {};
  function img(z, x, y){
    const k = z + '/' + x + '_' + y;
    if (!(k in imgs)) imgs[k] = new Promise(res => { const b = T[k]; if (!b) return res(null); const i = new Image(); i.onload = () => res(i); i.onerror = () => res(null); i.src = 'data:image/webp;base64,' + b; });
    return imgs[k];
  }''', h, count=1, flags=re.S)
assert n == 1, '模板里找不到瓦片加载代码块'
h = h.replace("""if (typeof L === 'undefined') { el.innerHTML = '<p style="padding:16px">地图脚本没加载出来，刷新一下试试。</p>'; return; }""",
              "if (typeof L === 'undefined') { document.querySelector('.map-card').hidden = true; return; }")
h = h.replace('  // OFFLINE_HOOK', '''  const sm = document.getElementById('static-map'), st = document.getElementById('static-toggle');
  sm.hidden = true; st.hidden = false;
  st.addEventListener('click', () => { sm.hidden = !sm.hidden; st.textContent = sm.hidden ? '看静态总览图（可长按保存到相册）' : '收起静态总览图'; });''')
h = h.replace('<footer>', '<footer>离线版，不联网也能看（导航链接需要联网）。', 1) + '\n</html>\n'
name = re.sub(r'[\\/:*?"<>|]', '', re.sub('<[^>]+>', '', plan['title'])).strip() or 'trip'
out_p = os.path.join(trip, 'offline', f'{name}.html')
open(out_p, 'w').write(h)
print('offline ->', out_p, f'{os.path.getsize(out_p) / 1e6:.1f} MB')
