#!/usr/bin/env node
// 生成 og-image.png（社群分享縮圖）
// 用法：node generate-og.js

const { createCanvas, GlobalFonts } = require('@napi-rs/canvas');
const fs = require('fs');
const path = require('path');

// 載入 CJK 字體
GlobalFonts.loadFontsFromDir('/usr/share/fonts/truetype/');
GlobalFonts.loadFontsFromDir('/usr/share/fonts/opentype/');
const CJK = '"WenQuanYi Zen Hei"';

const data = JSON.parse(fs.readFileSync(path.join(__dirname, 'processed_data.json'), 'utf8'));

const ts = data.team_stats;
const sim = data.simulation;

const projWins = Math.round(ts.wins + ts.games_remaining * ts.win_rate);
const playoff  = Math.round(sim.prob_playoff * 100);
const champ    = Math.round(sim.prob_champ * 100);

const W = 1200, H = 630;
const canvas = createCanvas(W, H);
const ctx = canvas.getContext('2d');

// ── 背景漸層 ──
const bg = ctx.createLinearGradient(0, 0, W, H);
bg.addColorStop(0, '#1a0a2e');
bg.addColorStop(1, '#2d1060');
ctx.fillStyle = bg;
ctx.fillRect(0, 0, W, H);

// ── 裝飾光暈（左上 & 右下）──
function glow(x, y, r, color) {
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  g.addColorStop(0, color);
  g.addColorStop(1, 'transparent');
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
}
glow(0,   0,   380, 'rgba(123,63,196,.35)');
glow(W,   H,   400, 'rgba(0,229,255,.15)');

// ── 頂部細線 ──
ctx.strokeStyle = '#00e5ff';
ctx.lineWidth = 3;
ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(W, 0); ctx.stroke();

// ── 隊伍 / 網站標題 ──
ctx.textAlign = 'center';
ctx.fillStyle = '#ffffff';
ctx.font = `bold 38px WenQuanYi Zen Hei, sans-serif`;
ctx.fillText('新竹御嵿攻城獅  2025-26 賽季預測', W / 2, 90);

// ── 副標 ──
ctx.fillStyle = 'rgba(197,184,220,.7)';
ctx.font = `22px WenQuanYi Zen Hei, sans-serif`;
ctx.fillText(`Monte Carlo 300,000 次模擬 · Pythagorean ^13.91 · 已賽 ${ts.wins}勝${ts.losses}負（剩 ${ts.games_remaining} 場）`, W / 2, 138);

// ── 三欄數據 ──
const cols = [
  { id: projWins + ' 勝', label: '預測本季\n最終勝場',  accent: '#00e5ff' },
  { id: playoff + '%',    label: '進季後賽\n機率',       accent: '#ffffff' },
  { id: champ  + '%',     label: '🏆  奪冠\n機率',       accent: '#f0c040' },
];

const colW  = W / 3;
const numY  = 330;
const lblY  = 430;

cols.forEach((col, i) => {
  const cx = colW * i + colW / 2;

  // 數字
  ctx.textAlign = 'center';
  ctx.fillStyle = col.accent;
  ctx.font = `bold 96px WenQuanYi Zen Hei, sans-serif`;
  ctx.fillText(col.id, cx, numY);

  // 標籤（換行）
  ctx.fillStyle = 'rgba(197,184,220,.85)';
  ctx.font = `bold 26px WenQuanYi Zen Hei, sans-serif`;
  col.label.split('\n').forEach((line, li) => {
    ctx.fillText(line, cx, lblY + li * 36);
  });

  // 分隔線
  if (i < 2) {
    ctx.strokeStyle = 'rgba(157,95,214,.4)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(colW * (i + 1), 210);
    ctx.lineTo(colW * (i + 1), 520);
    ctx.stroke();
  }
});

// ── 底部資訊列 ──
ctx.fillStyle = 'rgba(123,63,196,.3)';
ctx.fillRect(0, 570, W, 60);

ctx.fillStyle = 'rgba(197,184,220,.6)';
ctx.font = `18px WenQuanYi Zen Hei, sans-serif`;
ctx.textAlign = 'center';
ctx.fillText(`lioneer32232002-commits.github.io/lioneers-web  ·  資料截至 ${data.meta.generated}`, W / 2, 608);

// ── 輸出 ──
const out = path.join(__dirname, 'og-image.png');
fs.writeFileSync(out, canvas.toBuffer('image/png'));
console.log('✅  og-image.png 已生成 (' + W + 'x' + H + ')');
