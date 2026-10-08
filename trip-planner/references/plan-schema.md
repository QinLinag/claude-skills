# plan.json 字段（build_page / build_offline / make_phone_md 都读它）

```jsonc
{
  "title": "南京<em>一晚两天</em>",          // <em> 里的字用第 1 天的颜色强调；<title> 会自动去掉标签
  "kicker": "国庆 · 杭州 → 南京 · 两人 · 住一晚",
  "one_line": "一句话概括整趟怎么玩",
  "trip_cards": [                               // 页面顶部三张卡；day 决定顶边颜色（0=黑）
    {"label": "去程 · 10/1 周四", "big": "07:47 → 08:56", "sub": "G38 · 杭州东 → 南京南 · 出站坐 3 号线", "day": 1},
    {"label": "住 · 10/1 一晚", "big": "XX酒店", "sub": "XX路XX号 · 离XX站 350m · 可寄存", "day": 0},
    {"label": "回程 · 10/2 周五", "big": "19:00 → 20:01", "sub": "G235 · 检票口 A16 · 18:15 前过安检", "day": 2}
  ],
  "key_facts": [                                // 「标签：内容」；第一条以「出发前要办 / 已买的票」开头会变成顶部黄色待办框（用①②③分条）
    "已买的票：①六朝博物馆 → 同程；②夫子庙 → 小程序「南京夫子庙」；…",
    "夫子庙 2026 年新规：10/1–7 每天 14:00–22:00 核心区要预约…"
  ],
  "days": [{
    "date": "2026-10-01", "weekday": "周四", "theme": "…", "weather": "…",
    "route": ["nj_south", "changfujie", "hotel", "liuchao", "..."],   // 当天先后经过的 map_points id，地图连线用
    "segments": [{
      "time": "09:40–11:30", "title": "六朝博物馆", "place": "长江路302号",
      "getting_there": "…", "do_what": "…",
      "booking": "已买：同程 · 双人票…",                         // 写「不用预约」则页面不显示这一行
      "tips": ["…"],
      "plan_b": [{"trigger": "10:00 场没票", "alternative": "改去江宁织造博物馆…"}],
      "food_area_id": "d1_lunch",                                  // 可选，挂到 food_areas
      "map_ids": ["liuchao"]                                       // 「在地图上看」「高德导航」按钮用
    }]
  }],
  "food_areas": [{"id": "d1_lunch", "area": "大行宫 · 科巷", "meal": "10/1 午饭",
    "options": [{"name": "…", "branch": "…", "must_order": "…", "price_pp": "约22元", "why": "…", "queue": "…", "caution": "…"}]}],
  "must_eat": [{"dish": "盐水鸭", "where": "韩复兴（老门东）", "when": "10/2 下午"}],
  "bookings": [{"item": "…", "channel": "哪个 App/小程序", "rule": "…", "do_now": "现在/当天要做什么", "if_fail": "…"}],
  "contingencies": [{"scenario": "…", "action": "…"}],
  "map_points": [{
    "id": "hotel", "name": "XX酒店", "kind": "hotel",            // hotel | station | sight | night | food | alt
    "day": 0, "order": 0,                                          // sight/night 且 order>0 的点按 order 在当天编号 1,2,3…
    "geocode_query": "XX酒店 南京", "lat_wgs84": 32.0389, "lon_wgs84": 118.7882,
    "pin": true                                                    // 有 pin 就直接用给的坐标，不去查 OSM
  }],
  "budget": [{"item": "…", "cost": "…"}],
  "packing": ["…"],
  "sources": [{"title": "…", "url": "…"}]
}
```

约定：
- `kind=station` 且名字里没有「地铁」的（火车站）画成黑色方块「站」，地铁站画成小「M」。
- `kind=alt` 或 `order=0` 的非美食点画成空心「备」，在「替代方案」筛选里显示。
- 计划改了（约不到、换餐厅），改 plan.json 后重跑 `build_page.py` → 重新发布同一个 Artifact 文件路径；离线版、plan.md、服务器上的副本也要一起重新生成，别让各处内容对不上。
