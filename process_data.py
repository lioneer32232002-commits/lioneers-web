"""
新竹攻城獅 2025-26 賽季數據處理腳本
輸出 processed_data.json 供網站使用
"""
import json, sys, os
from collections import defaultdict
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

LION = '新竹御嵿攻城獅'
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
game_files = sorted([
    f for f in os.listdir(DATA_DIR)
    if f.endswith('.txt') and f not in
    ['lioneer_player.txt', 'lioneer.basic.txt', '20260330_allteam.txt']
])

# ================================================================
# 1. 解析所有比賽
# ================================================================
player_vs_opp_pm = defaultdict(lambda: defaultdict(list))
player_stats     = defaultdict(lambda: defaultdict(list))
games = []

STAT_KEYS = ['score', 'rebounds', 'assists', 'steals', 'blocks',
             'turnovers', 'plus_minus', 'field_goals_percentage',
             'three_pointers_made', 'three_pointers_attempted',
             'free_throws_percentage', 'efficiency', 'tsp', 'time_on_court']

for fname in game_files:
    with open(os.path.join(DATA_DIR, fname), encoding='utf-8') as f:
        d = json.load(f)
    ht, at = d['home_team'], d['away_team']
    if   ht['name'] == LION: lion, opp_team, is_home = ht, at, True
    elif at['name'] == LION: lion, opp_team, is_home = at, ht, False
    else: continue

    opp_name   = opp_team['name']
    lt         = lion['teams']['total']
    lion_score = lt['won_score']
    opp_score  = lt['lost_score']
    won        = lion_score > opp_score

    rounds_data = {int(k): v.get('won_score', 0)
                   for k, v in lion['teams']['rounds'].items()}

    date_str = fname.replace('.txt', '')
    if len(date_str) == 4:
        date_str = '2026' + date_str

    games.append({
        'date': date_str, 'opp': opp_name,
        'lion_score': lion_score, 'opp_score': opp_score,
        'won': won, 'is_home': is_home, 'rounds': rounds_data
    })

    for pid, p in lion['players']['total'].items():
        pname = p['name']
        pm    = p.get('plus_minus') or 0
        player_vs_opp_pm[pname][opp_name].append(pm)
        for sk in STAT_KEYS:
            v = p.get(sk)
            if v is not None:
                player_stats[pname][sk].append(float(v))

def mean(x): return round(sum(x)/len(x), 2) if x else 0

# ================================================================
# 2. 聯盟排名（從 allteam 檔案）
# ================================================================
with open(os.path.join(DATA_DIR, '20260330_allteam.txt'), encoding='utf-8') as f:
    allteams = json.load(f)

standings_raw = [
    {'name': t['team']['name'],
     'wins': t['won_game_count'],
     'losses': t['lost_game_count'],
     'gp': t['game_count']}
    for t in allteams
]
standings_sorted = sorted(standings_raw, key=lambda x: -x['wins'])

print('=== 聯盟排名 ===')
for i, t in enumerate(standings_sorted):
    marker = ' ← 攻城獅' if t['name'] == LION else ''
    print(f"{i+1}. {t['name']}: {t['wins']}W {t['losses']}L{marker}")

# ================================================================
# 3. 攻城獅本季統計
# ================================================================
wins            = sum(g['won'] for g in games)
losses          = len(games) - wins
gp              = len(games)
games_remaining = 36 - gp
win_rate        = wins / gp
avg_pts         = mean([g['lion_score'] for g in games])
avg_opp_pts     = mean([g['opp_score']  for g in games])

print(f'\n=== 攻城獅 {wins}W {losses}L, 剩 {games_remaining} 場 ===')

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
# 5. 球員熱力圖資料
# ================================================================
teams_order = ['高雄全家海神', '臺北台新戰神', '新北國王',
               '新北中信特攻', '福爾摩沙夢想家', '桃園台啤永豐雲豹']

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
# 7. TPBL 正確賽制 Monte Carlo 模擬（10萬次，NumPy 向量化）
# ================================================================
# 賽制說明：
# - 例行賽：36場（18主18客），前3直接進季後賽
# - 季後挑戰賽：第4 vs 第5，Bo3，第4先獲1勝（只需再贏1場）
#   場地：第1場5th主場，第2場4th主場，第3場5th主場（若有需要）
# - 季後賽：(1 vs 挑戰賽勝者) 與 (2 vs 3)，各 Bo5（三勝制），主場 2-2-1
# - 總冠軍賽：Bo7（四勝制），主場 2-2-1-1-1
# 主場優勢：+5% 勝率加成

np.random.seed(42)
N = 100_000
HOME_ADV = 0.05   # 主場優勢加成

team_list  = [t['name']  for t in standings_raw]
wins_now   = np.array([t['wins']  for t in standings_raw], dtype=np.float64)
games_left = np.array([36 - t['gp'] for t in standings_raw], dtype=np.int32)
wr_arr     = np.array(
    [t['wins'] / t['gp'] if t['gp'] > 0 else 0.5 for t in standings_raw],
    dtype=np.float64
)

lion_idx = team_list.index(LION)

# 向量化：一次模擬所有球隊剩餘場次
extra_wins = np.column_stack([
    np.random.binomial(int(gl), float(wr), size=N)
    for gl, wr in zip(games_left, wr_arr)
]).astype(np.float64)

final_wins_mat = wins_now[None, :] + extra_wins   # (N, n_teams)
rng = np.random.default_rng(42)

def win_prob(wr_a, wr_b, home_team_a=True):
    """計算 A 隊勝率，考量主場優勢"""
    base = wr_a / (wr_a + wr_b + 1e-9)
    adj  = base + HOME_ADV if home_team_a else base - HOME_ADV
    return float(np.clip(adj, 0.05, 0.95))

def sim_game(t_a, t_b, home_is_a=True):
    """模擬單場比賽，回傳 True 代表 A 勝"""
    p = win_prob(wr_arr[team_list.index(t_a)],
                 wr_arr[team_list.index(t_b)],
                 home_is_a)
    return rng.random() < p

def sim_play_in(t4, t5):
    """
    季後挑戰賽：t4 先獲1勝
    場地順序：5th主場 → 4th主場 → 5th主場
    t4 需再贏1場；t5 需贏2場
    """
    # Game 1 at t5 home
    if sim_game(t4, t5, home_is_a=False):   # t4 wins at t5 home -> t4 total 2 wins
        return t4
    # Game 2 at t4 home
    if sim_game(t4, t5, home_is_a=True):    # t4 wins at home -> t4 total 2 wins
        return t4
    # Game 3 at t5 home (t4=1win, t5=2wins -> t5 wins series)
    return t5

def sim_series_bo5(t_high, t_low):
    """
    五戰三勝，主場分配 2-2-1（戰績較優者 t_high 有多1場主場）
    主場順序：H H A A H
    """
    home_seq = [True, True, False, False, True]  # True = t_high is home
    wins_h, wins_l = 0, 0
    for is_high_home in home_seq:
        if wins_h == 3 or wins_l == 3:
            break
        if sim_game(t_high, t_low, home_is_a=is_high_home):
            wins_h += 1
        else:
            wins_l += 1
    return t_high if wins_h >= 3 else t_low

def sim_series_bo7(t_high, t_low):
    """
    七戰四勝，主場分配 2-2-1-1-1
    主場順序：H H A A H A H
    """
    home_seq = [True, True, False, False, True, False, True]
    wins_h, wins_l = 0, 0
    for is_high_home in home_seq:
        if wins_h == 4 or wins_l == 4:
            break
        if sim_game(t_high, t_low, home_is_a=is_high_home):
            wins_h += 1
        else:
            wins_l += 1
    return t_high if wins_h >= 4 else t_low

# 模擬計數
playoff_count    = 0   # 進季後賽（含透過挑戰賽）
semifinal_count  = 0   # 打季後賽半決賽
final_count      = 0   # 打進總冠軍賽
champ_count      = 0   # 拿冠軍
play_in_count    = 0   # 進挑戰賽（第4或第5）

for i in range(N):
    fw     = final_wins_mat[i]
    rank   = sorted(team_list, key=lambda x: -fw[team_list.index(x)])
    lion_r = rank.index(LION) + 1   # 1-based rank

    # 第6、7名直接淘汰
    if lion_r >= 6:
        continue

    # --- 季後挑戰賽 ---
    playoff_qualifier = None  # 挑戰賽勝者
    if lion_r in (4, 5):
        play_in_count += 1
        t4, t5 = rank[3], rank[4]
        winner = sim_play_in(t4, t5)
        if winner != LION:
            continue           # 攻城獅挑戰賽落敗，淘汰
        playoff_qualifier = LION
        playoff_count += 1
    else:
        # 前3名直接進季後賽
        playoff_count += 1
        playoff_qualifier = rank[3] if rank[3] != rank[4] else sim_play_in(rank[3], rank[4])
        # 取得挑戰賽勝者（不影響攻城獅，但影響對手）
        playoff_qualifier = sim_play_in(rank[3], rank[4])

    # --- 季後賽半決賽 ---
    # 第1名 vs 挑戰賽勝者；第2名 vs 第3名
    t1, t2, t3 = rank[0], rank[1], rank[2]
    challenger = playoff_qualifier  # 挑戰賽勝者當第4席

    # 確定攻城獅在哪一組
    if lion_r == 1:
        # 攻城獅 vs 挑戰賽勝者
        sf_winner_a = sim_series_bo5(t_high=LION, t_low=challenger)
        sf_winner_b = sim_series_bo5(t_high=t2, t_low=t3)
    elif lion_r == 2:
        sf_winner_a = sim_series_bo5(t_high=t1, t_low=challenger)
        sf_winner_b = sim_series_bo5(t_high=LION, t_low=t3)
    elif lion_r == 3:
        sf_winner_a = sim_series_bo5(t_high=t1, t_low=challenger)
        sf_winner_b = sim_series_bo5(t_high=t2, t_low=LION)
    else:
        # 攻城獅是挑戰賽勝者（challenger == LION）
        sf_winner_a = sim_series_bo5(t_high=t1, t_low=LION)
        sf_winner_b = sim_series_bo5(t_high=t2, t_low=t3)

    if LION not in (sf_winner_a, sf_winner_b):
        continue   # 半決賽落敗
    semifinal_count += 1

    # --- 總冠軍賽（Bo7）---
    # 戰績較優者（例行賽排名較高者）主場多
    if LION == sf_winner_a:
        # 攻城獅在A組贏，對上B組
        opp_final = sf_winner_b
        lion_rank_val  = fw[lion_idx]
        opp_rank_val   = fw[team_list.index(opp_final)]
        t_high = LION if lion_rank_val >= opp_rank_val else opp_final
        t_low  = opp_final if t_high == LION else LION
    else:
        opp_final = sf_winner_a
        lion_rank_val = fw[lion_idx]
        opp_rank_val  = fw[team_list.index(opp_final)]
        t_high = LION if lion_rank_val >= opp_rank_val else opp_final
        t_low  = opp_final if t_high == LION else LION

    champ = sim_series_bo7(t_high=t_high, t_low=t_low)
    final_count += 1
    if champ == LION:
        champ_count += 1

prob_play_in  = play_in_count  / N
prob_playoff  = playoff_count  / N
prob_semif    = semifinal_count / N
prob_final    = final_count    / N
prob_champ    = champ_count    / N

print(f'\n=== TPBL 正確賽制 Monte Carlo ({N:,} 次) ===')
print(f'進挑戰賽（第4/5名）: {prob_play_in:.1%}')
print(f'進季後賽（前3或挑戰賽勝）: {prob_playoff:.1%}')
print(f'打進季後賽半決賽:   {prob_semif:.1%}')
print(f'打進總冠軍賽:       {prob_final:.1%}')
print(f'🏆 拿下總冠軍:      {prob_champ:.1%}')

# ================================================================
# 8. ROC 曲線（上半場得分差 → 預測最終勝負）
# ================================================================
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
    rl = lion['teams']['rounds']
    ro = opp['teams']['rounds']
    half_lion = sum(rl[str(q)]['won_score'] for q in [1, 2] if str(q) in rl)
    half_opp  = sum(ro[str(q)]['won_score'] for q in [1, 2] if str(q) in ro)
    roc_points.append({'score': half_lion - half_opp, 'won': int(g['won'])})

scores = np.array([r['score'] for r in roc_points])
labels = np.array([r['won']   for r in roc_points])
thresholds = np.sort(np.unique(np.concatenate([scores - .5, scores + .5])))[::-1]

P, N_neg = labels.sum(), (labels == 0).sum()
roc_curve = []
for th in thresholds:
    pred = (scores >= th).astype(int)
    tp = int(((pred == 1) & (labels == 1)).sum())
    fp = int(((pred == 1) & (labels == 0)).sum())
    roc_curve.append({
        'fpr': round(fp / N_neg if N_neg else 0, 4),
        'tpr': round(tp / P    if P    else 0, 4)
    })

roc_sorted = sorted(roc_curve, key=lambda x: x['fpr'])
auc = sum(
    (roc_sorted[i+1]['fpr'] - roc_sorted[i]['fpr']) *
    (roc_sorted[i+1]['tpr'] + roc_sorted[i]['tpr']) / 2
    for i in range(len(roc_sorted)-1)
)
print(f'\nROC AUC = {auc:.3f}')

# ================================================================
# 9. 下一場 vs 特攻 勝率
# ================================================================
next_opp     = '新北中信特攻'
lion_wr_val  = float(win_rate)
opp_wr_val   = float(wr_arr[team_list.index(next_opp)])
next_prob_model = lion_wr_val / (lion_wr_val + opp_wr_val)

vs_next    = vs_record[next_opp]
hist_total = vs_next['w'] + vs_next['l']
hist_wr    = vs_next['w'] / hist_total if hist_total else 0.5
next_prob_adj = 0.6 * next_prob_model + 0.4 * hist_wr

print(f'\n下一場 vs {next_opp}: 模型 {next_prob_model:.1%} / 加權 {next_prob_adj:.1%}')

# ================================================================
# 10. 輸出 JSON
# ================================================================
output = {
    'meta': {'generated': '2026-04-01', 'total_games': gp, 'games_remaining': games_remaining},
    'team_stats': {
        'wins': int(wins), 'losses': int(losses),
        'games_played': gp, 'games_remaining': games_remaining,
        'avg_pts': avg_pts, 'avg_opp_pts': avg_opp_pts,
        'win_rate': round(lion_wr_val, 4)
    },
    'standings': standings_sorted,
    'games': games,
    'vs_summary': vs_summary,
    'heatmap': heatmap_data,
    'heatmap_teams': teams_order,
    'player_avg': player_season_avg,
    'simulation': {
        'prob_play_in':  round(float(prob_play_in),  4),
        'prob_playoff':  round(float(prob_playoff),  4),
        'prob_semif':    round(float(prob_semif),    4),
        'prob_final':    round(float(prob_final),    4),
        'prob_champ':    round(float(prob_champ),    4),
        'n_simulations': N,
        'rules': {
            'regular_season': '36場（18主18客），前3直接進季後賽',
            'play_in': '第4 vs 第5，Bo3，第4先獲1勝',
            'semifinal': 'Bo5（5戰3勝），主場分配 2-2-1',
            'championship': 'Bo7（7戰4勝），主場分配 2-2-1-1-1'
        }
    },
    'roc': {'curve': roc_sorted, 'auc': round(float(auc), 4)},
    'next_game': {
        'opponent': next_opp,
        'win_prob_model':    round(float(next_prob_model), 4),
        'win_prob_adjusted': round(float(next_prob_adj),   4),
        'historical_w': int(vs_next['w']),
        'historical_l': int(vs_next['l'])
    }
}

out_path = os.path.join(os.path.dirname(__file__), 'processed_data.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f'\n>>> processed_data.json 輸出完成')
