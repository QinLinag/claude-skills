"""plan.json 的 map_points -> points_gcj.json（GCJ-02 坐标，给高德底图用）。

    python3 geocode_points.py <行程目录> <城市>

规则：
- 点上写了 "pin": true 且有 lat_wgs84/lon_wgs84 → 直接用（酒店这类 OSM 查不到的点，自己用附近地铁站推算后钉住）。
- 否则依次用 geocode_query / name 去 Nominatim 查；结果离 agent 给的坐标太远（美食 >0.8km、其他 >1.2km）就当成同名的别处，丢掉。
- 都查不到就用 agent 给的近似坐标；美食点会标 approx，页面上提示「位置为片区大致位置」。
结果缓存在 <行程目录>/geo_cache.json，重复跑不重复请求。
"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo import nominatim, wgs2gcj, city_viewbox

trip, city = sys.argv[1], sys.argv[2]
plan = json.load(open(os.path.join(trip, 'plan.json')))
cache_p = os.path.join(trip, 'geo_cache.json')
cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}
vb = cache.get('__viewbox__') or city_viewbox(city)
cache['__viewbox__'] = vb


def dist_km(a, b):
    return math.hypot((a[0] - b[0]) * 111, (a[1] - b[1]) * 111 * math.cos(math.radians(a[0])))


def lookup(q):
    if q not in cache:
        try:
            cache[q] = [(float(x['lat']), float(x['lon']), x['display_name']) for x in nominatim(q, vb)]
        except Exception as ex:
            print('  ERR', q, ex)
            return []
        json.dump(cache, open(cache_p, 'w'), ensure_ascii=False)
    return cache[q]


out = []
for p in plan['map_points']:
    guess = (p.get('lat_wgs84'), p.get('lon_wgs84'))
    has_guess = all(isinstance(v, (int, float)) for v in guess)
    pick, approx, how = None, False, ''
    if p.get('pin') and has_guess:
        pick, how = guess, 'pin'
    else:
        names = [p.get('geocode_query'), p['name'], p['name'].split('（')[0].split('(')[0]]
        for q in dict.fromkeys(n for n in names if n):
            res = lookup(q)
            if not res:
                continue
            if has_guess:
                res = sorted(res, key=lambda r: dist_km(r[:2], guess))
                if dist_km(res[0][:2], guess) > (0.8 if p['kind'] == 'food' else 1.2):
                    continue
            pick, how = res[0][:2], f'osm:{q}'
            break
        if not pick and has_guess:
            pick, approx, how = guess, p['kind'] == 'food', 'agent'
    if not pick:
        print(f"  跳过（没有坐标）：{p['id']} {p['name']}")
        continue
    g = wgs2gcj(*pick)
    out.append({'id': p['id'], 'name': p['name'], 'kind': p['kind'], 'day': p.get('day', 0), 'order': p.get('order', 0),
                'lat': round(g[0], 6), 'lon': round(g[1], 6), 'approx': approx})
    print(f"  {p['id']:<16} {p['kind']:<7} {how:<28} {p['name']}")
json.dump(out, open(os.path.join(trip, 'points_gcj.json'), 'w'), ensure_ascii=False, indent=1)
print(len(out), 'points ->', os.path.join(trip, 'points_gcj.json'))
