export const meta = {
  name: 'trip-research',
  description: '旅行规划：多路并行调研（攻略/小红书/美食/交通天气）→ 合成主线计划 + 每段替代方案 → 挑错核查（只出问题清单）',
  whenToUse: '由 trip-planner skill 调用；args 里给 today、ctx（固定事实）、topics（调研分工）',
  phases: [
    { title: 'Research', detail: '按 topics 并行调研' },
    { title: 'Synthesize', detail: '合成 plan.json（主线 + Plan B + 分区美食）' },
    { title: 'Verify', detail: '挑错：只返回问题和修法，由主 agent 改' },
  ],
}

// args: { today: '2026-09-29', ctx: '固定事实 + 用户偏好（多行文本）', topics: [{ key, prompt }], extra_rules?: '额外要求' }
const A = args || {}
const TOPICS = Array.isArray(A.topics) ? A.topics : []
if (!TOPICS.length) throw new Error('args.topics 不能为空')

const CTX = `今天是 ${A.today}（北京时间）。
${A.ctx}
【工具约束】只用 WebSearch / WebFetch（以及 Bash 里的 curl）查资料；不要使用 Chrome 浏览器工具（只有明确授权的那一路可以用浏览器，避免抢同一个浏览器）。输出中文。关键结论尽量附来源 URL 和年份，别把旧规则当新规则。`

phase('Research')
const research = (await parallel(TOPICS.map(t => () =>
  agent(`${CTX}\n\n【你的任务】\n${t.prompt}`, { label: `research:${t.key}`, phase: 'Research' })
    .then(text => ({ key: t.key, text }))
))).filter(r => r && r.text)
log(`调研完成 ${research.length}/${TOPICS.length} 路`)
const BLOB = research.map(r => `===== 调研：${r.key} =====\n${r.text}`).join('\n\n')

const SEG = {
  type: 'object',
  properties: {
    time: { type: 'string', description: '如 08:56–09:40' },
    title: { type: 'string' },
    place: { type: 'string' },
    getting_there: { type: 'string', description: '从上一站怎么来：地铁几号线几站几分钟 / 打车多少钱多少分钟 / 步行多远' },
    do_what: { type: 'string', description: '做什么、看什么、多久' },
    booking: { type: 'string', description: '要不要预约/买票、在哪个 App、放票规则；不需要就写「不用预约」' },
    tips: { type: 'array', items: { type: 'string' } },
    plan_b: { type: 'array', items: { type: 'object', properties: {
      trigger: { type: 'string', description: '什么情况下启用：没约到/限流/下雨/太累/晚点' },
      alternative: { type: 'string', description: '具体替代做法：去哪、怎么去' },
    }, required: ['trigger', 'alternative'] } },
    food_area_id: { type: 'string' },
    map_ids: { type: 'array', items: { type: 'string' } },
  },
  required: ['time', 'title', 'place', 'getting_there', 'do_what', 'plan_b'],
}
const PLAN_SCHEMA = {
  type: 'object',
  properties: {
    title: { type: 'string', description: '短标题，如「南京一晚两天」，可含 <em>…</em> 强调' },
    kicker: { type: 'string', description: '如「国庆 · 杭州 → 南京 · 两人 · 住一晚」' },
    one_line: { type: 'string' },
    trip_cards: { type: 'array', items: { type: 'object', properties: {
      label: { type: 'string' }, big: { type: 'string' }, sub: { type: 'string' }, day: { type: 'integer', description: '对应第几天的颜色，酒店写 0' },
    }, required: ['label', 'big', 'sub'] }, description: '去程/住/回程三张卡' },
    key_facts: { type: 'array', items: { type: 'string' }, description: '「标签：内容」格式；第一条可以是「出发前要办：①…②…」' },
    days: { type: 'array', items: { type: 'object', properties: {
      date: { type: 'string' }, weekday: { type: 'string' }, theme: { type: 'string' }, weather: { type: 'string' },
      segments: { type: 'array', items: SEG },
      route: { type: 'array', items: { type: 'string' }, description: '当天按顺序经过的 map_points id（含酒店、车站），用于地图连线' },
    }, required: ['date', 'theme', 'segments', 'route'] } },
    food_areas: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, area: { type: 'string' }, meal: { type: 'string' },
      options: { type: 'array', items: { type: 'object', properties: {
        name: { type: 'string' }, branch: { type: 'string' }, must_order: { type: 'string' }, price_pp: { type: 'string' },
        why: { type: 'string' }, queue: { type: 'string' }, caution: { type: 'string' },
      }, required: ['name', 'must_order', 'why'] } },
    }, required: ['id', 'area', 'meal', 'options'] } },
    must_eat: { type: 'array', items: { type: 'object', properties: { dish: { type: 'string' }, where: { type: 'string' }, when: { type: 'string' } }, required: ['dish', 'where'] } },
    bookings: { type: 'array', items: { type: 'object', properties: {
      item: { type: 'string' }, channel: { type: 'string' }, rule: { type: 'string' }, do_now: { type: 'string' }, if_fail: { type: 'string' },
    }, required: ['item', 'channel', 'if_fail'] } },
    contingencies: { type: 'array', items: { type: 'object', properties: { scenario: { type: 'string' }, action: { type: 'string' } }, required: ['scenario', 'action'] } },
    map_points: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, name: { type: 'string' },
      kind: { type: 'string', enum: ['hotel', 'station', 'sight', 'night', 'food', 'alt'] },
      day: { type: 'integer', description: '第几天；两天都用写 0' },
      order: { type: 'integer', description: '主线顺序；备选写 0' },
      geocode_query: { type: 'string', description: '地理编码查询词，如「六朝博物馆 南京」' },
      lat_wgs84: { type: 'number' }, lon_wgs84: { type: 'number' },
    }, required: ['id', 'name', 'kind', 'day', 'order', 'geocode_query'] } },
    budget: { type: 'array', items: { type: 'object', properties: { item: { type: 'string' }, cost: { type: 'string' } }, required: ['item', 'cost'] } },
    packing: { type: 'array', items: { type: 'string' } },
    sources: { type: 'array', items: { type: 'object', properties: { title: { type: 'string' }, url: { type: 'string' } }, required: ['title'] } },
  },
  required: ['title', 'one_line', 'key_facts', 'days', 'food_areas', 'bookings', 'contingencies', 'map_points', 'sources'],
}

const RULES = `【计划要求】
- 节奏：每天 3–4 个核心点，步行总量尽量 ≤10km，中间留歇脚；可去可不去的点放进 plan_b 或 kind=alt，不要塞进主线。
- 一条清晰主线，从到达到离开；每段至少 1 个、关键段 2 个 Plan B（触发条件 + 具体去哪 + 怎么去）。
- 主线不能依赖「大概率约不到」的东西（热门景点临近出发往往已约满）；这类放成「刷到回流票再加」的可选项。
- 返程车次是硬约束：倒推写清「最晚几点必须往车站走」，节假日至少留 45 分钟进站余量。
- 每一餐挂一个 food_areas，每个至少 4 家：必点、人均、为什么推荐（引用评价）、排队、避雷；早饭店要真的早开门。
- bookings 写清在哪个 App/小程序、放票规则、用户现在该做什么、约不到的后路。
- map_points 覆盖酒店、车站、主线每个点、每个 food_areas 至少 1 个代表店、主要备选点；给出你所知的 WGS84 坐标（后面会再校正）。id 用简短英文。
- days[].route 按当天实际先后列出 map_points id（含酒店、地铁站、车站），用于地图连线。
- 时间要现实：排队、步行、换乘都算进去。中文输出，语气直接。sources 汇总最有价值的 10–25 条。
${A.extra_rules || ''}`

phase('Synthesize')
const plan = await agent(`${CTX}\n你是这趟行程的总规划师。下面是各路调研原文（可能互相矛盾：用更新、更具体、有来源的那条，冲突写进 tips）。\n${RULES}\n\n${BLOB}`,
  { label: 'synthesize:plan', phase: 'Synthesize', schema: PLAN_SCHEMA })

phase('Verify')
const ISSUES = {
  type: 'object',
  properties: { issues: { type: 'array', items: { type: 'object', properties: {
    where: { type: 'string', description: '定位：如 days[0].segments[3] / food_areas[d1_dinner] / bookings[2]' },
    severity: { type: 'string', enum: ['high', 'medium', 'low'] },
    problem: { type: 'string' },
    fix: { type: 'string', description: '具体改法（改成什么）' },
    source: { type: 'string' },
  }, required: ['where', 'severity', 'problem', 'fix'] } } },
  required: ['issues'],
}
// 只要问题清单：让核查 agent 重写整份几万字的 JSON 会长时间无输出而被判定卡死
const verify = plan ? await agent(`${CTX}\n你是挑剔的行程审核员。逐项找出下面计划里会翻车的地方，只返回问题清单（不要重写计划）：
1. 时间可行性：交通 + 排队 + 游览加起来排不排得下；到站后出站/寄存要多久；返程进站余量够不够。
2. 开放时间/闭馆日/最晚入场；夜游几点结束。
3. 预约现实性：主线有没有依赖大概率约不到的东西。
4. 人流：是否在最挤的时段去最挤的地方；地铁限流/封站风险。
5. 美食：是否顺路、营业时间是否对得上那一餐、是否倒闭搬迁、是否游客陷阱。
6. Plan B 是否具体可执行。7. 节奏是否太满（每天 >4 个核心点或步行 >10km 要指出）。8. map_points 坐标是否明显离谱。
必要时用 WebSearch/WebFetch 核实（不要用浏览器），每条尽量附来源。

===== 计划 =====
${JSON.stringify(plan)}

===== 调研原文（供核对）=====
${BLOB}`, { label: 'verify:issues', phase: 'Verify', schema: ISSUES }) : null

return { plan, issues: verify ? verify.issues : [], research }
