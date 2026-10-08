"""Geocoding helpers: Nominatim (OSM, returns WGS84) + WGS84 -> GCJ-02 (高德/腾讯底图用的坐标系).

    python3 geo.py 南京 "六朝博物馆" "中山陵"     # 快速试查（第一个参数是城市）
"""
import json, math, sys, time, urllib.parse, urllib.request

A = 6378245.0
EE = 0.00669342162296594323
UA = {'User-Agent': 'trip-planner-skill/1.0 (personal trip map, low volume)'}


def _tl(x, y):
    r = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    r += (20 * math.sin(6 * x * math.pi) + 20 * math.sin(2 * x * math.pi)) * 2 / 3
    r += (20 * math.sin(y * math.pi) + 40 * math.sin(y / 3 * math.pi)) * 2 / 3
    r += (160 * math.sin(y / 12 * math.pi) + 320 * math.sin(y * math.pi / 30)) * 2 / 3
    return r


def _tn(x, y):
    r = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    r += (20 * math.sin(6 * x * math.pi) + 20 * math.sin(2 * x * math.pi)) * 2 / 3
    r += (20 * math.sin(x * math.pi) + 40 * math.sin(x / 3 * math.pi)) * 2 / 3
    r += (150 * math.sin(x / 12 * math.pi) + 300 * math.sin(x / 30 * math.pi)) * 2 / 3
    return r


def wgs2gcj(lat, lon):
    """WGS84 -> GCJ-02. 中国境内的高德瓦片都是 GCJ-02，不转换标记会偏几百米。"""
    dlat, dlon = _tl(lon - 105, lat - 35), _tn(lon - 105, lat - 35)
    rl = lat / 180 * math.pi
    m = 1 - EE * math.sin(rl) ** 2
    sm = math.sqrt(m)
    dlat = dlat * 180 / ((A * (1 - EE)) / (m * sm) * math.pi)
    dlon = dlon * 180 / (A / sm * math.cos(rl) * math.pi)
    return lat + dlat, lon + dlon


def nominatim(q, viewbox=None, limit=3):
    """viewbox = (west, north, east, south)；给了就只在框内找。Nominatim 要求 ≤1 次/秒。"""
    params = {'q': q, 'format': 'json', 'limit': limit, 'countrycodes': 'cn', 'accept-language': 'zh'}
    if viewbox:
        params.update({'viewbox': ','.join(map(str, viewbox)), 'bounded': 1})
    req = urllib.request.Request('https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode(params), headers=UA)
    time.sleep(1.1)
    return json.loads(urllib.request.urlopen(req, timeout=20).read())


def city_viewbox(city, half=0.35):
    r = nominatim(city, limit=1)
    if not r:
        raise SystemExit(f'查不到城市：{city}')
    lat, lon = float(r[0]['lat']), float(r[0]['lon'])
    return (lon - half, lat + half, lon + half, lat - half)


if __name__ == '__main__':
    city, *qs = sys.argv[1:]
    vb = city_viewbox(city)
    for q in qs:
        print(q, '->', [(x['display_name'][:40], round(float(x['lat']), 5), round(float(x['lon']), 5)) for x in nominatim(q, vb)])
