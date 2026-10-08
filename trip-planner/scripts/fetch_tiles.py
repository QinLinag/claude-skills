"""按行程里的点下载高德中文底图瓦片（GCJ-02），打包成按需加载的 JSON 区块。

    python3 fetch_tiles.py <行程目录>

输入 <行程目录>/points_gcj.json，输出：
- <行程目录>/site/tiles/{z}/{x>>2}_{y>>2}.json   每个区块 4×4 张瓦片，值是 base64 PNG（网页按需 fetch）
- <行程目录>/tiles_meta.json                      区块索引、瓦片清单、覆盖范围
瓦片缓存在 ~/.cache/trip-planner/amap/，多次行程共用。

为什么不直接引用高德瓦片 URL：Artifact 页面的 CSP 禁止外部图片，只能把瓦片随页面一起发布。
覆盖策略：z11–15 尽量覆盖全部点的外接矩形；范围太大时退化为每个点周围一小块；z16 只给主线点和美食点周围约 600m。
"""
import base64, concurrent.futures as cf, json, math, os, sys, time, urllib.request

trip = sys.argv[1]
pts = json.load(open(os.path.join(trip, 'points_gcj.json')))
CACHE = os.path.expanduser('~/.cache/trip-planner/amap')
os.makedirs(CACHE, exist_ok=True)
OUT = os.path.join(trip, 'site', 'tiles')


def tile(lat, lon, z):
    n = 2 ** z
    return (int((lon + 180) / 360 * n),
            int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n))


def box_tiles(z, s, w, n, e):
    x0, y0 = tile(n, w, z)
    x1, y1 = tile(s, e, z)
    return {(z, x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}


lats = [p['lat'] for p in pts]
lons = [p['lon'] for p in pts]
S, N, W, E = min(lats), max(lats), min(lons), max(lons)
# zoom: (外接矩形外扩, 单点模式半径, 外接矩形模式最多瓦片数)
PLAN = {11: (0.10, 0.10, 40), 12: (0.06, 0.06, 60), 13: (0.03, 0.04, 120), 14: (0.015, 0.025, 250), 15: (0.008, 0.012, 450)}
jobs = set()
for z, (pad, rad, cap) in PLAN.items():
    full = box_tiles(z, S - pad, W - pad, N + pad, E + pad)
    if len(full) <= cap:
        jobs |= full
    else:
        for p in pts:
            jobs |= box_tiles(z, p['lat'] - rad, p['lon'] - rad, p['lat'] + rad, p['lon'] + rad)
for p in pts:
    if p['kind'] != 'alt':
        r = 0.006
        jobs |= box_tiles(16, p['lat'] - r, p['lon'] - r, p['lat'] + r, p['lon'] + r)
jobs = sorted(jobs)
print('tiles needed:', len(jobs), {z: sum(1 for j in jobs if j[0] == z) for z in range(11, 17)})
if len(jobs) > 1500:
    print('⚠️ 瓦片超过 1500 张，离线版会很大；考虑删掉离城区很远的备选点后重跑')


def get(j):
    z, x, y = j
    p = os.path.join(CACHE, f'{z}_{x}_{y}.png')
    if os.path.exists(p) and os.path.getsize(p) > 0:
        return j, True
    u = f'https://webrd0{1 + (x + y) % 4}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}'
    for attempt in range(3):
        try:
            data = urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=15).read()
            if data[:4] == b'\x89PNG':
                open(p, 'wb').write(data)
                return j, True
        except Exception:
            time.sleep(1 + attempt)
    return j, False


bad = []
with cf.ThreadPoolExecutor(6) as ex:
    for j, ok in ex.map(get, jobs):
        if not ok:
            bad.append(j)
if bad:
    print('下载失败', len(bad), bad[:5])

chunks = {}
for z, x, y in jobs:
    p = os.path.join(CACHE, f'{z}_{x}_{y}.png')
    if os.path.exists(p):
        chunks.setdefault((z, x // 4, y // 4), {})[f'{x}_{y}'] = base64.b64encode(open(p, 'rb').read()).decode()
index = {}
for (z, cx, cy), d in chunks.items():
    os.makedirs(os.path.join(OUT, str(z)), exist_ok=True)
    json.dump(d, open(os.path.join(OUT, str(z), f'{cx}_{cy}.json'), 'w'), separators=(',', ':'))
    index.setdefault(str(z), []).append(f'{cx}_{cy}')
meta = {'index': index, 'tiles': [f'{z}/{x}_{y}' for z, x, y in jobs if (z, x, y) not in bad],
        'bbox': [S, W, N, E]}
json.dump(meta, open(os.path.join(trip, 'tiles_meta.json'), 'w'))
total = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(OUT) for f in fs)
print(f'chunks {len(chunks)}  {total / 1e6:.1f} MB -> {OUT}')
