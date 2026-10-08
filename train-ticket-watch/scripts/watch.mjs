#!/usr/bin/env node
// 12306 余票监控：按日期/线路/发车时段/座位/人数轮询 12306（经 12306-mcp），
// 有车次从「不够」变成「够」时打印提醒并退出（exit 0），由调用方读输出、提醒用户、再带 --prev 重启。
//
// 用法：
//   node watch.mjs --date 2026-10-01 --from 杭州 --to 南京 --start 05:00 --end 14:00 --min 2 --once
//   node watch.mjs --date 2026-10-01 --from 杭州 --to 南京 --start 05:00 --end 14:00 --min 2 --interval 10 --prev "G38:一等座"
//
// 参数：
//   --date YYYY-MM-DD     出发日期（北京时间）。凌晨 0–6 点发的车属于当天日期。
//   --from / --to         城市名（杭州 = 全部杭州站）或具体站名（杭州东）。
//   --start / --end HH:MM 发车时段，含 start 不含 end。默认 00:00–24:00。
//   --seats a,b,c         关心的座位，默认 二等座,一等座,优选一等座（不含商务座、无座）。写 all 表示全部含无座。
//   --min N               至少几张才算有票（几个人一起走就填几）。默认 1。
//   --types GDC           车型：G 高铁/城际，D 动车，Z/T/K 普速，空=全部。默认 GD。
//   --exclude-stations a,b  排除的到站或发站（如 苏州南）。
//   --interval S          轮询间隔秒，默认 10；查询出错自动退避 60 秒。
//   --prev "车次:座位,..." 上一轮已经有票的组合，这些不重复提醒（重启时传上次输出的 ALL=）。
//   --cooldown S          同一车次座位两次提醒的最小间隔，默认 300 秒（防止同一张票反复闪烁刷屏）。
//   --until "YYYY-MM-DD HH:MM"  北京时间，到点自动停止。默认 = 出发日期 + end 时刻。
//   --once                只查一次：打印时段内全部车次和余票，然后退出。
//   --state-dir DIR       日志和冷却记录目录，默认 ~/.cache/train-ticket-watch
import { spawn } from 'node:child_process';
import { appendFileSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

const args = {};
for (let i = 2; i < process.argv.length; i++) {
  const k = process.argv[i];
  if (!k.startsWith('--')) continue;
  const v = process.argv[i + 1];
  if (v === undefined || v.startsWith('--')) { args[k.slice(2)] = true; } else { args[k.slice(2)] = v; i++; }
}
const need = ['date', 'from', 'to'];
for (const k of need) if (!args[k]) { console.error(`缺少参数 --${k}`); process.exit(64); }

const DATE = args.date, FROM = args.from, TO = args.to;
const START = args.start || '00:00', END = args.end || '24:00';
const SEATS = (args.seats && args.seats !== true ? args.seats : '二等座,一等座,优选一等座');
const ALL_SEATS = SEATS === 'all';
const WANT = new Set(ALL_SEATS ? [] : SEATS.split(','));
const MIN = +(args.min || 1);
const TYPES = args.types === true ? '' : (args.types ?? 'GD');
const EXCL = new Set(args['exclude-stations'] && args['exclude-stations'] !== true ? args['exclude-stations'].split(',') : []);
const INTERVAL = +(args.interval || 10) * 1000;
const COOLDOWN = +(args.cooldown ?? 300) * 1000;
const ONCE = !!args.once;
const STATE = args['state-dir'] || join(homedir(), '.cache', 'train-ticket-watch');
mkdirSync(STATE, { recursive: true });
const TAG = `${DATE}_${FROM}-${TO}`.replace(/[^\w一-龥-]/g, '_');
const LOG = join(STATE, `${TAG}.log`);
const CD_FILE = join(STATE, `${TAG}.cooldown.json`);

const bj = (d = new Date()) => d.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
const log = s => { try { appendFileSync(LOG, `[${bj()}] ${s}\n`); } catch {} };
const mins = s => +s.slice(0, 2) * 60 + +s.slice(3, 5);
const left = n => n === '有' ? 99 : (/^\d+$/.test(String(n)) ? +n : 0);
const leftTxt = n => n === '有' ? '20+ 张' : `${n} 张`;
const dur = l => { const [h, m] = String(l).split(':'); return `${+h}h${m}`; };
const inWindow = t => mins(t.start_time) >= mins(START) && mins(t.start_time) < (END === '24:00' ? 1440 : mins(END));
const seatOk = p => (ALL_SEATS || WANT.has(p.seat_name)) && left(p.num) >= MIN;
// --until 默认为出发日期 + END（北京时间，UTC+8）
const untilStr = args.until && args.until !== true ? args.until : `${DATE} ${END === '24:00' ? '23:59' : END}`;
const UNTIL = new Date(untilStr.replace(' ', 'T') + ':00+08:00');

let p = null, buf = '', id = 0; const pending = new Map();
function startMcp() {
  p = spawn('npx', ['-y', '12306-mcp'], { stdio: ['pipe', 'pipe', 'ignore'] });
  buf = '';
  p.stdout.on('data', d => {
    buf += d; let i;
    while ((i = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, i); buf = buf.slice(i + 1);
      if (!line.trim()) continue;
      try { const m = JSON.parse(line); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } } catch {}
    }
  });
  p.on('exit', () => { p = null; });
}
const rpc = (method, params, ms = 30000) => new Promise((res, rej) => {
  if (!p) return rej(new Error('12306-mcp 未运行'));
  const i = ++id;
  const t = setTimeout(() => { pending.delete(i); rej(new Error('timeout')); }, ms);
  pending.set(i, m => { clearTimeout(t); res(m); });
  p.stdin.write(JSON.stringify({ jsonrpc: '2.0', id: i, method, params }) + '\n');
});
async function init() {
  startMcp();
  await rpc('initialize', { protocolVersion: '2024-11-05', capabilities: {}, clientInfo: { name: 'train-ticket-watch', version: '1' } }, 90000);
  p.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n');
}
async function query() {
  if (!p) await init();
  const r = await rpc('tools/call', { name: 'get-tickets', arguments: { date: DATE, fromStation: FROM, toStation: TO, trainFilterFlags: TYPES, format: 'json' } });
  if (r.error) throw new Error(JSON.stringify(r.error));
  const txt = (r.result?.content || []).map(c => c.text).join('');
  let arr;
  try { arr = JSON.parse(txt); } catch { throw new Error('12306 返回非 JSON: ' + txt.slice(0, 120)); }
  return arr.filter(t => inWindow(t) && !EXCL.has(t.to_station) && !EXCL.has(t.from_station));
}
// 一行提醒：发车时间放最前面，方便用户在 App 里按时间快速定位
const line = (t, seats) => `**${t.start_time} 发车** · ${t.start_train_code} · ${t.from_station} → ${t.to_station}（${t.arrive_time} 到，${dur(t.lishi)}）· ` +
  seats.map(s => `${s.seat_name} ${s.price} 元 · 剩 ${leftTxt(s.num)}`).join(' / ');
const quit = code => { try { p?.kill(); } catch {} process.exit(code); };

if (ONCE) {
  try {
    await init();
    const arr = (await query()).sort((a, b) => mins(a.start_time) - mins(b.start_time));
    const ok = arr.map(t => ({ t, seats: t.prices.filter(seatOk) })).filter(x => x.seats.length);
    console.log(`SNAPSHOT 北京时间 ${bj()} | ${DATE} ${FROM}→${TO} ${START}–${END} | 座位 ${ALL_SEATS ? '全部' : [...WANT].join('/')} ≥${MIN} 张`);
    console.log(`时段内共 ${arr.length} 班，满足条件 ${ok.length} 班`);
    for (const x of ok) console.log(line(x.t, x.seats));
    // 其他还有票但不满足条件的（比如只有商务座/无座/张数不够），给用户做参考
    const other = arr.filter(t => !ok.some(x => x.t === t)).map(t => ({ t, s: t.prices.filter(q => left(q.num) > 0) })).filter(x => x.s.length);
    if (other.length) {
      console.log(`--- 不满足条件但还有票的 ${other.length} 班（商务座/无座/张数不够）---`);
      for (const x of other) console.log(`${x.t.start_time} ${x.t.start_train_code} ` + x.s.map(q => `${q.seat_name} ${q.price}(${q.num})`).join(' '));
    }
    console.log('ALL=' + ok.flatMap(x => x.seats.map(s => `${x.t.start_train_code}:${s.seat_name}`)).join(','));
    quit(0);
  } catch (e) { console.log('ERROR ' + e.message); quit(1); }
}

let prev = new Set(args.prev && args.prev !== true ? args.prev.split(',').filter(Boolean) : []);
let cd = {}; try { cd = JSON.parse(readFileSync(CD_FILE, 'utf8')); } catch {}
log(`START ${DATE} ${FROM}→${TO} ${START}–${END} seats=${SEATS} min=${MIN} interval=${INTERVAL / 1000}s until=${untilStr} prev=${[...prev].join(',')}`);
await init().catch(e => log('初始化失败: ' + e.message));
let n = 0;
while (true) {
  n++;
  let backoff = 0;
  try {
    const arr = await query();
    const ok = arr.map(t => ({ t, seats: t.prices.filter(seatOk) })).filter(x => x.seats.length);
    const key = (t, s) => `${t.start_train_code}:${s.seat_name}`;
    const cur = new Set(ok.flatMap(x => x.seats.map(s => key(x.t, s))));
    const now = Date.now();
    const fresh = ok.map(x => ({ ...x, seats: x.seats.filter(s => !prev.has(key(x.t, s)) && now - (cd[key(x.t, s)] || 0) > COOLDOWN) })).filter(x => x.seats.length);
    prev = cur;
    if (fresh.length) {
      fresh.forEach(x => x.seats.forEach(s => { cd[key(x.t, s)] = now; }));
      try { writeFileSync(CD_FILE, JSON.stringify(cd)); } catch {}
      const lines = fresh.map(x => line(x.t, x.seats));
      log(`#${n} HIT\n` + lines.join('\n'));
      console.log(`HIT 北京时间 ${bj()}（第 ${n} 次检查）`);
      console.log(lines.join('\n'));
      console.log('ALL=' + [...cur].join(','));
      quit(0);
    }
    log(`#${n} 无新票（时段内 ${arr.length} 班，当前满足条件 ${cur.size} 个）`);
  } catch (e) {
    log(`#${n} 查询出错: ${e.message}`);
    try { p?.kill(); } catch {} p = null;
    backoff = 60000;
  }
  if (new Date() > UNTIL) {
    console.log(`STOP 已到 ${untilStr}（北京时间），自动停止监控。`);
    console.log('ALL=' + [...prev].join(','));
    quit(0);
  }
  await new Promise(r => setTimeout(r, backoff || INTERVAL));
}
