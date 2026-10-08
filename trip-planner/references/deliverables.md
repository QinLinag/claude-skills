# 交付物细节

## 1. 网页 + 地图（Artifact）
- 生成：`geocode_points.py` → `fetch_tiles.py` → `build_page.py`（见 SKILL.md）。
- 发布：`Artifact(file_path=<T>/site/index.html, root=<T>/site, files=[{"path": "tiles/16/xxx_yyy.json"}, ...], icon="map")`。files 用 `find <T>/site/tiles -name '*.json'` 列出，一次最多 255 个。之后改计划就重新发布同一个 file_path，链接不变。
- 发布前本地预览：在 `site/` 起 `python3 -m http.server`，复制一份 index.html 并在开头补 `<!doctype html><meta charset="utf-8"><meta name="viewport" ...>`（Artifact 发布时会自动包这层，本地不补就是乱码），用浏览器看：瓦片清晰、标记落在对的地名上、筛选按钮和「在地图上看」能用。
- 地图原理（排查用）：Artifact 的 CSP 禁外链图片，所以把高德瓦片（GCJ-02）下载后打包成 JSON 随页发布、fetch 按需加载；Leaflet 自定义 GridLayer 在 canvas 上画，缺级时裁上级瓦片放大；坐标从 WGS84 转 GCJ-02。

## 2. 截图版流程（聊天里直接给）
用户原话：「简短又详细，我截图，不需要每次都看 html；要有时间、干什么、拿出什么票、票是哪个 App 买的，方便我快速掏出」。格式：

```
**出门必带**：两人身份证原件、充电宝、折叠伞
**今晚开通**：南京地铁乘车码（支付宝/微信小程序「南京地铁」）

## 📅 10/1 周四
**07:47** 杭州东 G38 → **08:56** 南京南，17 车
🎫 刷身份证进站（12306）

**09:40** 打车 5 分钟到 **六朝博物馆**，赶 10:00 免费讲解
🎫 **同程** → 六朝博物馆双人票（两个码，一人一个），**10:00 前进馆**
...
⏰ **15:55 定闹钟**：「钟山风景区」小程序刷回流票
...
## 🎫 票在哪个 App
- **同程**：六朝博物馆、科举博物馆
- **美团**：钟山四景联票、狮王府订座
- **小程序「南京夫子庙」**：夫子庙预约
- **现场买**：鸡鸣寺、台城、中华门瓮城
```
要点：每步两行以内；加粗时间和地点；票的那一行永远写「哪个 App → 哪张票 → 注意事项（几个码/共用码/几点前进）」；硬时间（最晚出发）用 ⚠️。

## 3. 离线单文件（发微信）
- `build_offline.py` 需要 Pillow：本机 python3 没有就 `python3 -m venv ~/.cache/trip-planner/venv && ~/.cache/trip-planner/venv/bin/pip install pillow`。
- 产物 `offline/<标题>.html`（约 8MB：WebP 瓦片 + Leaflet 内联）和 `offline/路线总览.jpg`。复制到 `~/Downloads` 并 `open -R` 让用户直接拖进微信。
- 告诉用户怎么在手机上看：
  - **iPhone**：微信里点开会预览（多半不跑脚本 → 自动显示静态路线图 + 全部文字）；想要能缩放的地图需要放到网址上用 Safari 打开（见第 5 条）。
  - **安卓**：微信里「…」→「用其他应用打开」→ 选 Chrome/系统浏览器/QQ 浏览器。
  - 路线总览图 JPG 让用户存相册，最稳。

## 4. 给手机 Claude 的随身计划
- `make_phone_md.py <T> "返程硬约束"` → `offline/plan.md`（十几 KB 纯文本）。网页 HTML 太大，手机 Claude 读不了，只给它 plan.md。
- 教用户：手机开代理 → Claude App 新建对话 → 上传 plan.md（或贴链接，若它抓不到 http/IP 链接就改传文件）→ 先考一句「X 号下午 4 点我该干嘛」确认读进去了 → 路上一直用这个对话语音问。
- 也可以在 claude.ai 建一个 Project 把 plan.md 放进项目知识，手机 App 里在这个 Project 下开对话。

## 5. 放到用户自己的服务器（可选，必须先征得同意）
- `scripts/host/deploy.sh <ssh-host> <T> <下线日期>`：上传 index.html(+gz)、plan.md、map.jpg 到 `/srv/trip-pages/<随机token>/`，起 `trip-pages` 服务（只认随机路径，其余 404，gzip 传输），到下线日期北京时间 00:00 自动删除。
- 说明风险：是公网 http 链接，拿到链接的人都能看；微信可能提示「非微信官方网页」，点继续或复制到 Safari。
- 服务器的 443 等端口可能被代理占用，用高端口；云厂商安全组要放行这个端口。

## 6. 天气与穿衣（出发前一天）
按 `references/weather-packing.md` 做：跑 `weather.py`，先用一两句话给结论（穿什么、带伞还是雨衣、雨落在哪段行程），再给预报表。结论同步写进 plan.json 的 `packing`/`weather`，截图版流程顶部的「出门必带」也要跟着改。

## 7. 预算格式
「已付（按订单）」+「路上估算」两张表，再列「可能多出来的」，最后给总价区间和人均。车票用 12306 查准确票价，不要估。
