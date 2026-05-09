#!/usr/bin/env node
// 生成 og-image.png（社群分享縮圖）
// 用法：node generate-og.js

const { createCanvas, GlobalFonts } = require('@napi-rs/canvas');
const fs = require('fs');
const path = require('path');

// 載入 CJK 字體
const fontDirs = [
  '/usr/share/fonts/truetype/',
  '/usr/share/fonts/opentype/',
  'C:\\Windows\\Fonts',
  process.env.LOCALAPPDATA ? path.join(process.env.LOCALAPPDATA, 'Microsoft', 'Windows', 'Fonts') : '',
].filter(Boolean);
fontDirs.forEach(d => { try { GlobalFonts.loadFontsFromDir(d); } catch(_) {} });
const CJK_CANDIDATES = [
  'WenQuanYi Zen Hei', 'Noto Sans CJK TC', 'Microsoft JhengHei',
  'Microsoft YaHei', 'PingFang TC', 'Heiti TC',
];
const loadedFamilies = GlobalFonts.families.map(f => f.family);
const CJK_NAME = CJK_CANDIDATES.find(n => loadedFamilies.includes(n)) || 'sans-serif';
const F = (size, weight = 'normal') => `${weight} ${size}px "${CJK_NAME}", sans-serif`;

const data = JSON.parse(fs.readFileSync(path.join(__dirname, 'processed_data.json'), 'utf8'));
const ps   = data.playoff_series;
const lgh  = data.last_game_hint;

const W = 1200, H = 630;
const canvas = createCanvas(W, H);
const ctx = canvas.getContext('2d');

// ── 背景 ──
const bg = ctx.createLinearGradient(0, 0, W, H);
bg.addColorStop(0, '#1a0a2e');
bg.addColorStop(1, '#2a1050');
ctx.fillStyle = bg;
ctx.fillRect(0, 0, W, H);

// 光暈
function glow(x, y, r, color) {
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  g.addColorStop(0, color);
  g.addColorStop(1, 'transparent');
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
}
glow(150,  80,  300, 'rgba(123,63,196,.30)');
glow(1050, 550, 280, 'rgba(0,229,255,.12)');
glow(600,  630, 250, 'rgba(123,63,196,.18)');

// ── 頂部青色細線 ──
ctx.strokeStyle = '#00e5ff';
ctx.lineWidth = 4;
ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(W, 0); ctx.stroke();

// ── 標題 ──
ctx.textAlign = 'center';
ctx.fillStyle = '#ffffff';
ctx.font = F(42, 'bold');
ctx.fillText('新竹御嵿攻城獅  2025-26 賽季', W / 2, 76);

ctx.fillStyle = 'rgba(197,184,220,.75)';
ctx.font = F(22);
ctx.fillText(`季後賽四強 Bo5 ・ 攻城獅 vs 夢想家`, W / 2, 118);

// ── 細分隔線 ──
ctx.strokeStyle = 'rgba(123,63,196,.35)';
ctx.lineWidth = 1;
ctx.beginPath(); ctx.moveTo(80, 142); ctx.lineTo(W - 80, 142); ctx.stroke();

// ================================================================
// 三欄佈局
// ================================================================
const colW = W / 3;
const MID_Y = 370;  // 主要內容垂直中心

// ── 左欄：系列賽比分 ──
const LX = colW / 2;  // 左欄中心 X

// lion_wins / opp_wins
const lw = ps ? ps.lion_wins  : 0;
const ow = ps ? ps.opp_wins   : 0;

// 大數字
ctx.textAlign = 'center';
ctx.font = F(130, 'bold');
ctx.fillStyle = '#00e5ff';
ctx.fillText(String(lw), LX - 55, MID_Y - 10);

ctx.fillStyle = 'rgba(197,184,220,.5)';
ctx.font = F(80, 'bold');
ctx.fillText(':', LX, MID_Y - 20);

ctx.fillStyle = '#f06292';
ctx.font = F(130, 'bold');
ctx.fillText(String(ow), LX + 55, MID_Y - 10);

// 球隊名稱
ctx.font = F(17);
ctx.fillStyle = 'rgba(0,229,255,.8)';
ctx.textAlign = 'center';
ctx.fillText('攻城獅', LX - 55, MID_Y + 34);
ctx.fillStyle = 'rgba(240,98,146,.8)';
ctx.fillText('夢想家', LX + 55, MID_Y + 34);

// ── 中欄：場次圓點 ──
const CX = colW + colW / 2;  // 中欄中心 X

ctx.font = F(15);
ctx.fillStyle = 'rgba(197,184,220,.6)';
ctx.textAlign = 'center';
ctx.fillText('場次進度', CX, 178);

const games  = ps ? ps.games : [];
const dotN   = games.length;
const dotR   = 30;
const dotGap = 18;
const dotTotalW = dotN * dotR * 2 + (dotN - 1) * dotGap;
const dotStartX = CX - dotTotalW / 2 + dotR;

games.forEach((g, i) => {
  const dx = dotStartX + i * (dotR * 2 + dotGap);
  const dy = MID_Y - 20;

  if (g.result === 'W') {
    // 勝：亮青填色
    ctx.beginPath(); ctx.arc(dx, dy, dotR, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(0,229,255,.15)';
    ctx.fill();
    ctx.strokeStyle = '#00e5ff';
    ctx.lineWidth = 2.5;
    ctx.stroke();
    // W 字
    ctx.fillStyle = '#00e5ff';
    ctx.font = F(22, 'bold');
    ctx.textAlign = 'center';
    ctx.fillText('W', dx, dy + 8);
  } else if (g.result === 'L') {
    ctx.beginPath(); ctx.arc(dx, dy, dotR, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(240,98,146,.15)';
    ctx.fill();
    ctx.strokeStyle = '#f06292';
    ctx.lineWidth = 2.5;
    ctx.stroke();
    ctx.fillStyle = '#f06292';
    ctx.font = F(22, 'bold');
    ctx.textAlign = 'center';
    ctx.fillText('L', dx, dy + 8);
  } else {
    // 未來場次：灰框
    ctx.beginPath(); ctx.arc(dx, dy, dotR, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,255,255,.04)';
    ctx.fill();
    ctx.strokeStyle = 'rgba(197,184,220,.25)';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    // 場次標籤
    ctx.fillStyle = 'rgba(197,184,220,.55)';
    ctx.font = F(15, 'bold');
    ctx.textAlign = 'center';
    ctx.fillText(g.label, dx, dy + 5);
  }

  // 日期 / 結果副標
  ctx.font = F(13);
  ctx.fillStyle = 'rgba(197,184,220,.5)';
  ctx.textAlign = 'center';
  const sub = g.result ? g.label : (g.date || '');
  ctx.fillText(sub, dx, dy + dotR + 18);
});

// ── 右欄：晉級率 ──
const RX = colW * 2 + colW / 2;  // 右欄中心 X

const prob  = ps ? Math.round(ps.series_win_prob * 100) : 0;
const need  = ps ? ps.need_to_win - ps.lion_wins : 3;
const needTxt = need > 0 ? `再贏 ${need} 場即晉級` : '已晉級！';

ctx.textAlign = 'center';
ctx.fillStyle = 'rgba(197,184,220,.6)';
ctx.font = F(17);
ctx.fillText('系列賽晉級率', RX, 178);

// 大機率數字
ctx.font = F(110, 'bold');
ctx.fillStyle = '#00e5ff';
ctx.fillText(prob + '%', RX, MID_Y + 10);

// 進度條
const barW = 220, barH = 10, barX = RX - barW / 2, barY = MID_Y + 42;
// 底
ctx.beginPath();
ctx.roundRect(barX, barY, barW, barH, 5);
ctx.fillStyle = 'rgba(255,255,255,.1)';
ctx.fill();
// 填色
const fillW = Math.round(barW * prob / 100);
if (fillW > 0) {
  const grad = ctx.createLinearGradient(barX, 0, barX + fillW, 0);
  grad.addColorStop(0, 'rgba(123,63,196,.9)');
  grad.addColorStop(1, '#00e5ff');
  ctx.beginPath();
  ctx.roundRect(barX, barY, fillW, barH, 5);
  ctx.fillStyle = grad;
  ctx.fill();
}

ctx.fillStyle = 'rgba(197,184,220,.6)';
ctx.font = F(16);
ctx.textAlign = 'center';
ctx.fillText(needTxt, RX, MID_Y + 78);

// 分隔線
[colW, colW * 2].forEach(x => {
  ctx.strokeStyle = 'rgba(123,63,196,.3)';
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(x, 150); ctx.lineTo(x, 520); ctx.stroke();
});

// ── 底部資訊列 ──
ctx.fillStyle = 'rgba(26,10,46,.85)';
ctx.fillRect(0, 570, W, 60);
ctx.strokeStyle = 'rgba(123,63,196,.4)';
ctx.lineWidth = 1;
ctx.beginPath(); ctx.moveTo(0, 570); ctx.lineTo(W, 570); ctx.stroke();

ctx.fillStyle = 'rgba(197,184,220,.5)';
ctx.font = F(17);
ctx.textAlign = 'center';
ctx.fillText(`lioneers-web.pages.dev  ·  資料截至 ${data.meta.generated}`, W / 2, 607);

// ── 輸出 ──
const out = path.join(__dirname, 'og-image.png');
fs.writeFileSync(out, canvas.toBuffer('image/png'));
console.log('✅  og-image.png 已生成 (' + W + 'x' + H + ')');
