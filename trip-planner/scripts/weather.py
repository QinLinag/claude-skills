"""出发前查天气，并按规则给出穿衣/装备建议。

    python3 weather.py <城市> <开始 YYYY-MM-DD> <结束 YYYY-MM-DD> [--spots 钟山风景区,玄武湖] [--up 400]

- 中国天气网（CMA）7 天预报：城市 + --spots 里的景区（景区有单独预报代码，山上/湖边用它更准）。只覆盖未来 7 天。
- Open-Meteo（按经纬度，免 key）：逐日最高/最低、体感温度、降水量/降水时长/概率、阵风、紫外线，
  以及白天每 3 小时的温度和「哪几个小时会下雨」。
- --up：要爬的山比市区高多少米（如钟山 ~400、黄山光明顶 ~1800），按每 100m 降 0.6℃ 估算山上温度。
两个来源不一致时，建议按更冷、更可能下雨的那个准备（脚本的建议就是这么取的）。
规则说明见 references/weather-packing.md。
"""
import argparse, json, os, re, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo import nominatim

ap = argparse.ArgumentParser()
ap.add_argument('city'); ap.add_argument('start'); ap.add_argument('end')
ap.add_argument('--spots', default='')
ap.add_argument('--up', type=float, default=0)
a = ap.parse_args()
UA = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.weather.com.cn/'}


def get(url, tries=3):
    for k in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read().decode('utf-8', 'ignore')
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(1.5)


def cma_code(name):
    for q in (name, name + '风景区', name + '景区'):
        try:
            t = get('https://toy1.weather.com.cn/search?cityname=' + urllib.parse.quote(q))
            refs = [r['ref'].split('~') for r in json.loads(t.strip()[1:-1])]
            if refs:
                return refs[0][0], refs[0][2]
        except Exception:
            pass
    return None, None


def cma_7d(code):
    s = get(f'https://www.weather.com.cn/weather/{code}.shtml')
    out = []
    for m in re.finditer(r'<h1>([^<]*)</h1>.*?<p title="([^"]*)" class="wea">.*?<p class="tem">(.*?)</p>.*?<p class="win">(.*?)</p>', s, re.S):
        tem = re.sub(r'<[^>]+>|\s', '', m.group(3))
        win = re.sub(r'<[^>]+>|\s', '', m.group(4))
        out.append((m.group(1), m.group(2), tem, win))
    return out


d0, d1 = int(a.start[8:10]), int(a.end[8:10])


def in_range(h1):
    """中国天气网的日期只有「1日（明天）」这样的日号；跨月时（如 30 号到 2 号）按首尾环绕判断。"""
    m = re.match(r'(\d+)日', h1)
    if not m:
        return False
    n = int(m.group(1))
    return d0 <= n <= d1 if d0 <= d1 else (n >= d0 or n <= d1)
cma_rain, cma_low = False, None
print('== 中国天气网 ==')
for name in [a.city] + [x for x in a.spots.split(',') if x]:
    code, cname = cma_code(name)
    if not code:
        print(f'  {name}: 查不到预报代码'); continue
    try:
        rows = [r for r in cma_7d(code) if in_range(r[0])]
    except Exception as ex:
        print(f'  {name}: 获取失败 {ex}'); continue
    if not rows:
        print(f'  {cname}: 出行日期不在 7 天预报范围内'); continue
    for h1, wea, tem, win in rows:
        print(f'  {cname} {h1} {wea} {tem} {win}')
        cma_rain |= '雨' in wea or '雪' in wea
        lows = [int(x) for x in re.findall(r'(-?\d+)℃', tem)]
        if lows:
            cma_low = min(lows) if cma_low is None else min(cma_low, min(lows))

r = nominatim(a.city, limit=1)
lat, lon = float(r[0]['lat']), float(r[0]['lon'])
q = urllib.parse.urlencode({'latitude': lat, 'longitude': lon, 'timezone': 'Asia/Shanghai', 'start_date': a.start, 'end_date': a.end,
    'daily': 'temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,precipitation_sum,precipitation_hours,'
             'precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,uv_index_max',
    'hourly': 'temperature_2m,apparent_temperature,precipitation_probability,precipitation,relative_humidity_2m,wind_speed_10m'})
d = json.loads(urllib.request.urlopen('https://api.open-meteo.com/v1/forecast?' + q, timeout=20).read())
dl, h = d['daily'], d['hourly']
bf = lambda kmh: next((i for i, v in enumerate([1, 6, 12, 20, 29, 39, 50, 62, 75, 89], 0) if kmh < v), 10)
print('\n== Open-Meteo（逐日 + 白天关键时段）==')
S = {'tmin': [], 'tmax': [], 'amin': [], 'act': [], 'rain': 0, 'pmax': 0, 'gust': 0, 'uv': 0, 'hum': 0, 'rain_windows': []}
for i, t in enumerate(dl['time']):
    print(f"{t}  {dl['temperature_2m_min'][i]:.0f}~{dl['temperature_2m_max'][i]:.0f}℃（体感 {dl['apparent_temperature_min'][i]:.0f}~{dl['apparent_temperature_max'][i]:.0f}℃）"
          f"  雨 {dl['precipitation_sum'][i]}mm/{dl['precipitation_hours'][i]:.0f}h 概率{dl['precipitation_probability_max'][i]}%"
          f"  阵风 {dl['wind_gusts_10m_max'][i]:.0f}km/h（约{bf(dl['wind_gusts_10m_max'][i])}级）  紫外线 {dl['uv_index_max'][i]}")
    S['tmin'].append(dl['temperature_2m_min'][i]); S['tmax'].append(dl['temperature_2m_max'][i]); S['amin'].append(dl['apparent_temperature_min'][i])
    S['rain'] = max(S['rain'], dl['precipitation_sum'][i] or 0); S['pmax'] = max(S['pmax'], dl['precipitation_probability_max'][i] or 0)
    S['gust'] = max(S['gust'], dl['wind_gusts_10m_max'][i] or 0); S['uv'] = max(S['uv'], dl['uv_index_max'][i] or 0)
    wet = []
    for j, ht in enumerate(h['time']):
        if not ht.startswith(t):
            continue
        hh = int(ht[11:13])
        if 7 <= hh <= 22:
            S['act'].append(h['apparent_temperature'][j])
            S['hum'] = max(S['hum'], h['relative_humidity_2m'][j] or 0)
            if (h['precipitation_probability'][j] or 0) >= 40 or (h['precipitation'][j] or 0) >= 0.3:
                wet.append(hh)
        if hh in (7, 10, 13, 16, 19, 22):
            print(f"   {ht[11:16]} {h['temperature_2m'][j]:.0f}℃ 体感{h['apparent_temperature'][j]:.0f}℃ 降雨概率{h['precipitation_probability'][j]}% "
                  f"{h['precipitation'][j]:.1f}mm 湿度{h['relative_humidity_2m'][j]}%")
    if wet:
        spans, st = [], wet[0]
        for k in range(1, len(wet) + 1):
            if k == len(wet) or wet[k] != wet[k - 1] + 1:
                spans.append(f'{st}–{wet[k - 1] + 1}点'); st = wet[k] if k < len(wet) else None
        print(f"   可能下雨的时段：{'、'.join(spans)}")
        S['rain_windows'].append(f"{t[5:]} {'、'.join(spans)}")

# ---- 建议（取更保守的值）
# 按出门活动的 7–22 点算；中国天气网的最低温出现在凌晨，+2℃ 折算到早上出门时再取更冷的那个
low = min(S['act'] or S['amin'])
if cma_low is not None:
    low = min(low, cma_low + 2)
high = max(S['tmax'])
swing = max(x - y for x, y in zip(S['tmax'], S['tmin']))
rainy = cma_rain or S['pmax'] >= 30 or S['rain'] >= 1
heavy = S['rain'] >= 10
windy = S['gust'] >= 39   # ≥6 级阵风：伞容易翻
mtn_low = low - 0.6 * a.up / 100 if a.up else None
print('\n== 建议 ==')
def layer(t):
    if t >= 28: return '短袖 + 防晒'
    if t >= 23: return '短袖或薄长袖'
    if t >= 18: return '长袖 + 一件薄外套（风衣/薄夹克/卫衣）'
    if t >= 12: return '长袖 + 厚一点的外套（夹克/卫衣外再加一件）'
    if t >= 5: return '毛衣/抓绒 + 厚外套'
    return '羽绒服 + 保暖内衣 + 帽子手套'
print(f'- 早晚（出门/夜游时体感约 {low:.0f}℃）：{layer(low)}')
print(f'- 中午（最高约 {high:.0f}℃）：{layer(high)}')
if swing >= 8:
    print(f'- 早晚温差约 {swing:.0f}℃：洋葱式穿法，外套要能脱下来塞进包里。')
if mtn_low is not None:
    print(f'- 山上（高出 {a.up:.0f}m）比市区冷约 {0.6 * a.up / 100:.1f}℃，最低约 {mtn_low:.0f}℃ → {layer(mtn_low)}；山顶和湖边风大，再加一层防风。')
if rainy:
    w = '；'.join(S['rain_windows']) or '见上方中国天气网'
    print(f'- 雨：会下雨（{w}）→ 每人一把折叠伞。')
    if heavy or windy:
        print('- 雨大或风大（伞容易翻），或行程里有爬山/坐船/长时间户外 → 加一次性雨衣，鞋子选防水防滑的，带一双备用袜子。')
    if heavy:
        print('- 雨量较大：把对应时段的户外点换成室内备选（博物馆/书店/商场），城墙和山路湿滑要少走。')
else:
    print('- 雨：基本不下，带一把折叠伞备用即可（晴雨两用也能挡太阳）。')
if windy:
    print(f'- 风：阵风约 {bf(S["gust"])} 级，外套选防风的；帽子容易被吹跑。')
if S['uv'] >= 6:
    print('- 紫外线强：防晒霜、帽子、墨镜。')
elif S['uv'] >= 3:
    print('- 紫外线中等：涂点防晒。')
if high >= 28 and S['hum'] >= 75:
    print('- 又热又潮：速干衣、多带一件替换的 T 恤。')
print('- 每次都带：身份证原件、充电宝（≤100Wh，随身）、纸巾湿巾、水、常用药（创可贴、肠胃药、晕车药按需）、好走防滑的鞋。')
