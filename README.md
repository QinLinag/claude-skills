# claude-skills

自己在用、觉得有用的 [Claude Code](https://claude.com/claude-code) skill 合集。每个文件夹是一个独立的 skill。

| Skill | 用来干什么 |
|---|---|
| [trip-planner](trip-planner/) | 国内出游的端到端规划：选目的地 → 定高铁 → 找酒店 → 多 agent 去小红书/知乎/攻略调研 → 「一条主线 + 每段替代方案 + 每餐多家可选」的计划 → 一个一个带你办预约并核对订单截图 → 交付带高德地图的网页、截图版流程、能发微信的离线单文件、给手机 Claude 的随身计划，以及按天气给出的穿衣和装备建议 |
| [train-ticket-watch](train-ticket-watch/) | 12306 余票监控：说日期、线路和时段，每 10 秒查一次，一有票就按「几点发车 · 车次 · 座位 · 剩几张」提醒你去 App 里抢（不替你下单） |

## 安装

把想用的 skill 文件夹放到 `~/.claude/skills/` 下，重开一个 Claude Code 会话就会自动出现：

```bash
git clone https://github.com/QinLinag/claude-skills.git
mkdir -p ~/.claude/skills
cp -r claude-skills/trip-planner claude-skills/train-ticket-watch ~/.claude/skills/
```

想跟着仓库更新，可以用软链接代替复制：`ln -s "$PWD/claude-skills/trip-planner" ~/.claude/skills/trip-planner`。

## 依赖

- **train-ticket-watch**：Node.js 18+（第一次运行会用 npx 自动下载 `12306-mcp`）。
- **trip-planner**：
  - Python 3（地图、页面、天气脚本只用标准库）；
  - 离线单文件需要 Pillow（`python3 -m venv ~/.cache/trip-planner/venv && ~/.cache/trip-planner/venv/bin/pip install pillow`）；
  - 多 agent 调研需要 Claude Code 的 Workflow 功能；看小红书需要 Claude in Chrome 扩展，并在自己的浏览器里登录小红书；
  - 车票部分会用到 train-ticket-watch。

## 说明

- 这些 skill 只帮你查信息、做计划、提醒，不会替你下单、付款或输入密码。
- 地图底图来自高德，地理编码用 OpenStreetMap Nominatim，天气用中国天气网和 Open-Meteo，请合理、低频使用。
