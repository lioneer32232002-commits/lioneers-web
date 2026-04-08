"""
產生 og-image.png（社群分享縮圖）
用法：python generate-og.py
"""
import json, sys, os
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))

# ── 讀資料 ──
data = json.load(open(os.path.join(BASE, 'processed_data.json'), encoding='utf-8'))
ts   = data['team_stats']
sim  = data['simulation']

proj_wins = round(ts['wins'] + ts['games_remaining'] * ts['win_rate'])
playoff   = round(sim['prob_playoff'] * 100)
champ     = round(sim['prob_champ']   * 100)

# ── 字體（微軟正黑體，Windows 內建）──
def font(size, bold=True):
    fp = 'C:/Windows/Fonts/msjhbd.ttc' if bold else 'C:/Windows/Fonts/msjh.ttc'
    try:    return ImageFont.truetype(fp, size, index=0)
    except: return ImageFont.load_default()

# ── 畫布 ──
W, H = 1200, 630
img  = Image.new('RGB', (W, H), '#1a0a2e')

# 背景光暈（左上）
overlay = Image.new('RGB', (W, H), '#1a0a2e')
od = ImageDraw.Draw(overlay)
od.ellipse((-320, -320, 320, 320), fill='#2d1560')
img = Image.blend(img, overlay, 0.5)

d = ImageDraw.Draw(img)

# 頂部青色線
d.line([(0, 0), (W, 0)], fill='#00e5ff', width=4)

# ── 標題 ──
d.text((W//2, 82),
       '新竹攻城獅  2025-26 賽季預測',
       font=font(44), fill='#ffffff', anchor='mm')
d.text((W//2, 138),
       f'Monte Carlo 300,000 次模擬 · 已賽 {ts["wins"]}勝{ts["losses"]}負（剩 {ts["games_remaining"]} 場）',
       font=font(26, bold=False), fill='#c5b8dc', anchor='mm')

# ── 三欄數據 ──
cols = [
    (str(proj_wins) + ' 勝', '預測本季\n最終勝場', '#00e5ff'),
    (str(playoff)   + '%',   '進季後賽\n機率',      '#ffffff'),
    (str(champ)     + '%',   '奪冠機率',            '#f0c040'),
]
col_w = W // 3
for i, (num, lbl, color) in enumerate(cols):
    cx = col_w * i + col_w // 2
    d.text((cx, 310), num, font=font(100), fill=color, anchor='mm')
    for li, line in enumerate(lbl.split('\n')):
        d.text((cx, 418 + li * 48), line,
               font=font(32, bold=False), fill='#c5b8dc', anchor='mm')
    if i < 2:
        d.line([(col_w*(i+1), 200), (col_w*(i+1), 520)],
               fill='#9d5fd6', width=1)

# ── 底部列 ──
d.rectangle([(0, 568), (W, 630)], fill='#3b1a6e')
d.text((W//2, 600),
       f'lioneers-web.pages.dev  ·  資料截至 {data["meta"]["generated"]}',
       font=font(20, bold=False), fill='#c5b8dc', anchor='mm')

# ── 輸出 ──
out = os.path.join(BASE, 'og-image.png')
img.save(out, 'PNG')
print(f'og-image.png 產生完成（{proj_wins}勝預測・季後賽{playoff}%・奪冠{champ}%）')
