import json, sys, os, math, random
from collections import defaultdict
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

LION = '新竹御嵿攻城獅'
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
game_files = sorted([
    f for f in os.listdir(DATA_DIR)
    if f.endswith('.txt') and f not in ['lioneer_player.txt', 'lioneer.basic.txt', '20260330_allteam.txt']
])

# ================================================================
# 1. 解析所有比賽
# ================================================================
player_vs_opp_pm = defaultdict(lambda: defaultdict(list))
player_stats = defaultdict(lambda: defaultdict(list))
games = []

STAT_KEYS = ['score','rebounds','assists','steals','blocks','turnovers',
             'plus_minus','field_goals_percentage','three_pointers_made',
             'three_pointers_attempted','free_throws_percentage',
             'efficiency','tsp','time_on_court']

for fname in game_files:
    with open(os.path.join(DATA_DIR, fname), encoding='utf-8') as f:
        d = json.load(f)
    ht, at = d['home_team'], d['away_team']
    if ht['name'] == LION:
        lion, opp_team = ht, at
    elif at['name'] == LION:
        lion, opp_team = at, ht
    else:
        continue

    opp_name = opp_team['name']
    lt = lion['teams']['total']
    lion_score = lt['won_score']
    opp_score  = lt['lost_score']
    won = lion_score > opp_score

    # 節次得分
    rounds_data = {}
    for rk, rv in lion['teams']['rounds'].items():
        rounds_data[int(rk)] = rv.get('won_score', 0)

    # 日期正規化
    date_str = fname.replace('.txt', '')
    if len(date_str) == 4:
        date_str = '2026' + date_str

    games.append({
        'date': date_str, 'opp': opp_name,
        'lion_score': lion_score, 'opp_score': opp_score,
        'won': won, 'rounds': rounds_data
    })

    for pid, p in lion['players']['total'].items():
        pname = p['name']
        pm = p.get('plus_minus') or 0
        player_vs_opp_pm[pname][opp_name].append(pm)
        for sk in STAT_KEYS:
            v = p.get(sk)
            if v is not None:
                player_stats[pname][sk].append(float(v))

def mean(x):
    return round(sum(x) / len(x), 2) if x else 0

# ================================================================
# 2. 讀取聯盟總積分榜
# ================================================================
with open(os.path.join(DATA_DIR, '20260330_allteam.txt'), encoding='utf-8') as f:
    allteams = json.load(f)

standings_raw = []
for t in allteams:
    standings_raw.append({
        'name': t['team']['name'],
        'wins': t['won_game_count'],
        'losses': t['lost_game_count'],
        'gp': t['game_count']
    })
standings_sorted = sorted(standings_raw, key=lambda x: -x['wins'])

print('=== 聯盟排名 ===')
for i, t in enumerate(standings_sorted):
    marker = ' ← 攻城獅' if t['name'] == LION else ''
    print(f"{i+1}. {t['name']}: {t['wins']}W {t['losses']}L{marker}")

# ================================================================
# 3. 攻城獅基本統計
# ================================================================
wins   = sum(g['won'] for g in games)
losses = len(games) - wins
gp     = len(games)
games_remaining = 36 - gp
win_rate = wins / gp

avg_pts     = mean([g['lion_score'] for g in games])
avg_opp_pts = mean([g['opp_score']  for g in games])

print(f'\n=== 攻城獅 {wins}W {losses}L, 剩 {games_remaining} 場 ===')
print(f'均得分 {avg_pts} 均失分 {avg_opp_pts}')

# ================================================================
# 4. 對各隊戰績
# ================================================================
vs_record = defaultdict(lambda: {'w': 0, 'l': 0, 'lp': [], 'op': []})
for g in games:
    r = vs_record[g['opp']]
    r['w' if g['won'] else 'l'] += 1
    r['lp'].append(g['lion_score'])
    r['op'].append(g['opp_score'])

vs_summary = {
    opp: {'w': r['w'], 'l': r['l'],
          'avg_lion': mean(r['lp']), 'avg_opp': mean(r['op'])}
    for opp, r in vs_record.items()
}

# ================================================================
# 5. 球員 vs 對手 plus_minus 熱力圖資料
# ================================================================
teams_order = ['高雄全家海神', '臺北台新戰神', '新北國王', '新北中信特攻', '福爾摩沙夢想家', '桃園台啤永豐雲豹']

# 只保留上場 >= 3 場的球員
key_players = [p for p, od in player_vs_opp_pm.items()
               if sum(len(v) for v in od.values()) >= 3]
key_players_sorted = sorted(
    key_players,
    key=lambda p: -mean([x for vs in player_vs_opp_pm[p].values() for x in vs])
)

heatmap_data = []
for pname in key_players_sorted:
    row = {'player': pname, 'values': {}}
    for opp in teams_order:
        vals = player_vs_opp_pm[pname].get(opp, [])
        row['values'][opp] = mean(vals) if vals else None
    heatmap_data.append(row)

# ================================================================
# 6. 球員賽季均值
# ================================================================
important_stats = ['score', 'rebounds', 'assists', 'steals', 'blocks',
                   'turnovers', 'plus_minus', 'efficiency', 'tsp',
                   'three_pointers_made', 'three_pointers_attempted']
player_season_avg = {}
for pname, stats in player_stats.items():
    n = len(stats.get('score', []))
    if n >= 3:
        player_season_avg[pname] = {
            sk: mean(stats[sk]) for sk in important_stats if stats.get(sk)
        }
        player_season_avg[pname]['games'] = n

# ================================================================
# 7. Monte Carlo 季後賽模擬 (100,000 次，NumPy 向量化)
# ================================================================
np.random.seed(42)
N = 100_000

team_list  = [t['name']  for t in standings_raw]
wins_now   = np.array([t['wins']  for t in standings_raw], dtype=np.float32)
games_left = np.array([36 - t['gp'] for t in standings_raw], dtype=np.int32)
wr_arr     = np.array([t['wins'] / t['gp'] if t['gp'] > 0 else 0.5
                        for t in standings_raw], dtype=np.float32)

lion_idx = team_list.index(LION)

# 向量化：shape (N, n_teams)
extra_wins = np.column_stack([
    np.random.binomial(int(gl), float(wr), size=N)
    for gl, wr in zip(games_left, wr_arr)
]).astype(np.float32)

final_wins_mat = wins_now[None, :] + extra_wins   # (N, n_teams)

# 排名 (降序) — argsort(-) 每行
ranks = np.argsort(-final_wins_mat, axis=1)       # (N, n_teams)
lion_ranks = np.argwhere(ranks == lion_idx)[:, 1] + 1  # 1-based

in_playoff   = lion_ranks <= 4                    # bool (N,)
prob_playoff = in_playoff.mean()

# 季後賽晉級模擬（有進季後賽的那些 simulation）
# 1st vs 4th, 2nd vs 3rd; Bo3 半決賽, Bo5 冠軍賽
playoff_mask = np.where(in_playoff)[0]
final_count = 0
champ_count = 0

for i in playoff_mask:
    fw = final_wins_mat[i]
    rank_teams = [team_list[j] for j in np.argsort(-fw)]
    playoff = rank_teams[:4]

    def sim_series(t1, t2, wins_needed):
        wr1 = float(wr_arr[team_list.index(t1)])
        wr2 = float(wr_arr[team_list.index(t2)])
        p = wr1 / (wr1 + wr2)
        w1 = w2 = 0
        while w1 < wins_needed and w2 < wins_needed:
            if np.random.random() < p:
                w1 += 1
            else:
                w2 += 1
        return t1 if w1 >= wins_needed else t2

    sf1 = sim_series(playoff[0], playoff[3], 2)  # Bo3
    sf2 = sim_series(playoff[1], playoff[2], 2)
    champ = sim_series(sf1, sf2, 3)              # Bo5

    if LION in (sf1, sf2):
        final_count += 1
    if champ == LION:
        champ_count += 1

prob_final = final_count / N
prob_champ = champ_count / N

print(f'\n=== 季後賽模擬 ({N:,} 次) ===')
print(f'進季後賽 (前4): {prob_playoff:.1%}')
print(f'打冠軍賽:       {prob_final:.1%}')
print(f'拿冠軍:         {prob_champ:.1%}')

# ================================================================
# 8. ROC Curve 資料 (用上半場得分差預測最終勝負)
# ================================================================
# 預測分數 = Q1+Q2 得分差（上半場領先），標籤 = 最終勝/負
roc_points = []
for g in games:
    raw_fname = None
    for fname in game_files:
        date_key = fname.replace('.txt', '')
        if len(date_key) == 4:
            date_key = '2026' + date_key
        if date_key == g['date']:
            raw_fname = fname
            break
    if raw_fname is None:
        continue
    with open(os.path.join(DATA_DIR, raw_fname), encoding='utf-8') as f:
        d = json.load(f)
    ht, at = d['home_team'], d['away_team']
    lion = ht if ht['name'] == LION else at
    opp  = at if ht['name'] == LION else ht
    rounds_lion = lion['teams']['rounds']
    rounds_opp  = opp['teams']['rounds']
    # 上半場 Q1+Q2
    half_lion = sum(rounds_lion[str(q)]['won_score'] for q in [1,2] if str(q) in rounds_lion)
    half_opp  = sum(rounds_opp[str(q)]['won_score']  for q in [1,2] if str(q) in rounds_opp)
    half_diff = half_lion - half_opp
    roc_points.append({'score': half_diff, 'won': 1 if g['won'] else 0})

# 計算ROC
scores = np.array([r['score'] for r in roc_points])
labels = np.array([r['won']   for r in roc_points])
thresholds = np.sort(np.unique(np.concatenate([scores - 0.5, scores + 0.5])))[::-1]
roc_curve = []
P = labels.sum()
N_neg = len(labels) - P
for th in thresholds:
    pred = (scores >= th).astype(int)
    tp = ((pred == 1) & (labels == 1)).sum()
    fp = ((pred == 1) & (labels == 0)).sum()
    tpr = float(tp / P)   if P > 0 else 0.0
    fpr = float(fp / N_neg) if N_neg > 0 else 0.0
    roc_curve.append({'fpr': round(fpr, 4), 'tpr': round(tpr, 4)})

# AUC (trapezoid)
roc_sorted = sorted(roc_curve, key=lambda x: x['fpr'])
auc = sum(
    (roc_sorted[i+1]['fpr'] - roc_sorted[i]['fpr']) *
    (roc_sorted[i+1]['tpr'] + roc_sorted[i]['tpr']) / 2
    for i in range(len(roc_sorted)-1)
)
print(f'\n=== ROC AUC: {auc:.3f} ===')

# ================================================================
# 9. 下一場 vs 特攻 勝率估計
# ================================================================
next_opp = '新北中信特攻'
lion_wr = win_rate
opp_wr  = wr_arr[team_list.index(next_opp)]
next_win_prob = float(lion_wr / (lion_wr + opp_wr))

# 歷史對戰紀錄加權
vs_next = vs_record[next_opp]
hist_wins  = vs_next['w']
hist_total = vs_next['w'] + vs_next['l']
hist_wr = hist_wins / hist_total if hist_total > 0 else 0.5
# 加權：歷史 40%, 勝率模型 60%
next_win_prob_adj = 0.6 * next_win_prob + 0.4 * hist_wr

print(f'\n=== 下一場 vs {next_opp} ===')
print(f'純勝率模型: {next_win_prob:.1%}')
print(f'加權(歷史+模型): {next_win_prob_adj:.1%}')
print(f'歷史對戰: {hist_wins}W {hist_total-hist_wins}L')

# ================================================================
# 10. 輸出最終 JSON
# ================================================================
output = {
    'meta': {
        'generated': '2026-04-01',
        'total_games': gp,
        'games_remaining': games_remaining
    },
    'team_stats': {
        'wins': int(wins), 'losses': int(losses),
        'games_played': gp, 'games_remaining': games_remaining,
        'avg_pts': avg_pts, 'avg_opp_pts': avg_opp_pts,
        'win_rate': round(float(win_rate), 4)
    },
    'standings': standings_sorted,
    'games': games,
    'vs_summary': vs_summary,
    'heatmap': heatmap_data,
    'heatmap_teams': teams_order,
    'player_avg': player_season_avg,
    'simulation': {
        'prob_playoff': round(float(prob_playoff), 4),
        'prob_final':   round(float(prob_final), 4),
        'prob_champ':   round(float(prob_champ), 4),
        'n_simulations': N
    },
    'roc': {
        'curve': roc_sorted,
        'auc': round(float(auc), 4)
    },
    'next_game': {
        'opponent': next_opp,
        'win_prob_model': round(float(next_win_prob), 4),
        'win_prob_adjusted': round(float(next_win_prob_adj), 4),
        'historical_w': hist_wins,
        'historical_l': hist_total - hist_wins
    }
}

out_path = os.path.join(os.path.dirname(__file__), 'processed_data.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f'\n>>> processed_data.json 輸出完成！({out_path})')
