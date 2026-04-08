"""
新竹攻城獅 2025-26 賽季數據處理腳本
輸出 processed_data.json 供網站使用
"""
import json, sys, os
from collections import defaultdict
import numpy as np
from scipy import stats as sp_stats

sys.stdout.reconfigure(encoding='utf-8')

LION     = '新竹御嵿攻城獅'
DEPARTED = {'克雷格', '李漢昇'}   # 已離隊球員（保留數據但標記）
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
EXCLUDE_FILES = {'lioneer_player.txt', 'lioneer.basic.txt',
                 '20260330_allteam.txt', '20260402_allgame.txt',
                 '20260402_allteam_update.txt', 'allteam_latest.txt'}
game_files = sorted([
    f for f in os.listdir(DATA_DIR)
    if f.endswith('.txt') and f not in EXCLUDE_FILES
])

# ================================================================
# 1. 解析所有比賽
# ================================================================
player_vs_opp_pm  = defaultdict(lambda: defaultdict(list))
player_vs_opp_ppp = defaultdict(lambda: defaultdict(list))
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

    rounds_data     = {int(k): v.get('won_score', 0)
                       for k, v in lion['teams']['rounds'].items()}
    opp_rounds_data = {int(k): v.get('won_score', 0)
                       for k, v in opp_team['teams']['rounds'].items()}

    # 得分來源（隊伍層級）
    ot = opp_team['teams']['total']
    paint   = lt.get('points_in_paint',      0) or 0
    fb_pts  = lt.get('fast_break_points',     0) or 0
    sc2_pts = lt.get('second_chance_points',  0) or 0
    ft_made = lt.get('free_throws_made',      0) or 0

    date_str = fname.replace('.txt', '')
    if len(date_str) == 4:
        date_str = '2026' + date_str

    games.append({
        'date': date_str, 'opp': opp_name,
        'lion_score': lion_score, 'opp_score': opp_score,
        'won': won, 'is_home': is_home,
        'rounds': rounds_data, 'opp_rounds': opp_rounds_data,
        'paint': paint, 'fast_break': fb_pts,
        'second_chance': sc2_pts, 'ft_made': ft_made,
    })

    # 全隊本場 FGA/FTA/TOV 總和（用於 USG% 計算）
    team_poss = sum(
        float(p.get('field_goals_attempted') or 0)
        + 0.44 * float(p.get('free_throws_attempted') or 0)
        + float(p.get('turnovers') or 0)
        for p in lion['players']['total'].values()
    )

    for pid, p in lion['players']['total'].items():
        pname = p['name']
        pm    = p.get('plus_minus') or 0
        player_vs_opp_pm[pname][opp_name].append(pm)
        # 計算個人 PPP（每回合得分）
        pts  = float(p.get('score') or 0)
        fga  = float(p.get('field_goals_attempted') or 0)
        oreb = float(p.get('offensive_rebounds') or 0)
        to_  = float(p.get('turnovers') or 0)
        fta  = float(p.get('free_throws_attempted') or 0)
        poss = fga - oreb + to_ + 0.44 * fta
        if poss > 0:
            player_vs_opp_ppp[pname][opp_name].append(round(pts / poss, 3))
        # 計算個人 USG%（= 個人持球回合 / 全隊持球回合 × 100）
        if team_poss > 0:
            usg = round((fga + 0.44 * fta + to_) / team_poss * 100, 1)
            player_stats[pname]['usg'].append(usg)
        for sk in STAT_KEYS:
            v = p.get(sk)
            if v is not None:
                player_stats[pname][sk].append(float(v))

def mean(x): return round(sum(x)/len(x), 2) if x else 0

# ================================================================
# 2. 聯盟排名（從最新 allteam 檔案）
# ================================================================
# 優先讀最新抓取的、否則 fallback 到手動版本
_allteam_candidates = ['allteam_latest.txt', '20260402_allteam_update.txt']
_allteam_file = next(
    (f for f in _allteam_candidates if os.path.exists(os.path.join(DATA_DIR, f))), None
)
if _allteam_file is None:
    raise FileNotFoundError('找不到 allteam 資料檔，請先執行 auto_update.py 或放入 allteam_update 檔')
with open(os.path.join(DATA_DIR, _allteam_file), encoding='utf-8') as f:
    allteams = json.load(f)

standings_raw = [
    {'name': t['team']['name'],
     'wins': t['won_game_count'],
     'losses': t['lost_game_count'],
     'gp': t['game_count']}
    for t in allteams
]
standings_sorted = sorted(
    standings_raw,
    key=lambda x: -(x['wins'] / x['gp'] if x['gp'] > 0 else 0)
)

print('=== 聯盟排名 ===')
for i, t in enumerate(standings_sorted):
    marker = ' ← 攻城獅' if t['name'] == LION else ''
    print(f"{i+1}. {t['name']}: {t['wins']}W {t['losses']}L{marker}")

# 各球隊進攻效率（每百回合估算：FGA − OREB + TO + 0.44×FTA）
league_rtg = []
for t in allteams:
    avg  = t['average_stats']
    fga  = avg.get('field_goals_attempted', 0) or 0
    oreb = avg.get('offensive_rebounds',    0) or 0
    to_v = avg.get('turnovers',             0) or 0
    fta  = avg.get('free_throws_attempted', 0) or 0
    poss = fga - oreb + to_v + 0.44 * fta
    pts  = avg.get('won_score',  0) or 0
    opp  = avg.get('lost_score', 0) or 0
    ortg   = round(pts / poss * 100, 1) if poss > 0 else 0.0
    drtg   = round(opp / poss * 100, 1) if poss > 0 else 0.0
    netrtg = round(ortg - drtg, 1)
    league_rtg.append({
        'name':   t['team']['name'],
        'wins':   t['won_game_count'],
        'losses': t['lost_game_count'],
        'gp':     t['game_count'],
        'ortg':   ortg,
        'drtg':   drtg,
        'netrtg': netrtg,
    })
league_rtg.sort(key=lambda x: -x['netrtg'])

# ================================================================
# 3. 攻城獅本季統計
# ================================================================
wins            = sum(g['won'] for g in games)
losses          = len(games) - wins
gp              = len(games)
# 以最新 allteam 檔取得攻城獅實際累積場次（更準確）
_lion_row        = next((t for t in standings_raw if t['name'] == LION), None)
lion_allgame_gp  = _lion_row['gp']   if _lion_row else gp
lion_total_wins  = _lion_row['wins'] if _lion_row else wins
lion_total_losses= _lion_row['losses'] if _lion_row else losses
games_remaining  = 36 - lion_allgame_gp
win_rate         = lion_total_wins / lion_allgame_gp if lion_allgame_gp > 0 else wins / gp
avg_pts          = mean([g['lion_score'] for g in games])
avg_opp_pts      = mean([g['opp_score']  for g in games])

print(f'\n=== 攻城獅 {lion_total_wins}W {lion_total_losses}L ({lion_allgame_gp} gp, 剩 {games_remaining} 場) ===')

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
               '新北中信特攻', '福爾摩沙夢想家', '桃園台啤永豐雲豹',
               '新竹御嵿攻城獅']

key_players = [p for p, od in player_vs_opp_pm.items()
               if sum(len(v) for v in od.values()) >= 3
               and p not in DEPARTED]
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

# PPP 熱力圖（同排序邏輯）
ppp_key_players = [p for p, od in player_vs_opp_ppp.items()
                   if sum(len(v) for v in od.values()) >= 3
                   and p not in DEPARTED]
ppp_score_fn = lambda v: (3 if v >= 1.3 else 2 if v >= 1.15 else 1 if v >= 1.0 else -1 if v >= 0.9 else -2 if v >= 0.8 else -3)
ppp_players_sorted = sorted(
    ppp_key_players,
    key=lambda p: (
        -sum(1 for vs in player_vs_opp_ppp[p].values() for _ in vs),  # 非null場次多的先
        -sum(ppp_score_fn(v) for vs in player_vs_opp_ppp[p].values() for v in vs)
    )
)
ppp_heatmap_data = []
for pname in ppp_players_sorted:
    row = {'player': pname, 'values': {}}
    for opp in teams_order:
        vals = player_vs_opp_ppp[pname].get(opp, [])
        row['values'][opp] = round(mean(vals), 3) if vals else None
    ppp_heatmap_data.append(row)

# ================================================================
# 6. 球員賽季均值
# ================================================================
important_stats = ['score', 'rebounds', 'assists', 'steals', 'blocks',
                   'turnovers', 'plus_minus', 'efficiency', 'tsp', 'usg',
                   'three_pointers_made', 'three_pointers_attempted']
player_season_avg = {}
for pname, stats in player_stats.items():
    n = len(stats.get('score', []))
    if n >= 3:
        player_season_avg[pname] = {
            sk: mean(stats[sk]) for sk in important_stats if stats.get(sk)
        }
        player_season_avg[pname]['games']    = n
        player_season_avg[pname]['departed'] = pname in DEPARTED

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

    semifinal_count += 1   # 所有進季後賽的隊都打半決賽

    if LION not in (sf_winner_a, sf_winner_b):
        continue   # 半決賽落敗

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
# 8. ROC 曲線（多個預測指標，含 Youden's J 最佳切點）
# ================================================================
# 從每場比賽萃取攻城獅隊伍級別數據
game_team_stats = []   # [{'won':bool, '得分':int, '三分命中率':float, ...}]

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
    lt = lion['teams']['total']

    three_att = lt.get('three_pointers_attempted', 0)
    three_pct = lt['three_pointers_made'] / three_att if three_att else 0
    fg_att = lt.get('field_goals_attempted', 0)
    fg_pct = lt['field_goals_made'] / fg_att if fg_att else 0

    game_team_stats.append({
        'won':        int(g['won']),
        '三分命中率': round(three_pct * 100, 1),
        '三分命中數': lt.get('three_pointers_made', 0),
        '整體命中率': round(fg_pct * 100, 1),
        '助攻':       lt.get('assists', 0),
        '失誤數':     lt.get('turnovers', 0),
        '籃板':       lt.get('rebounds', 0),
        '抄截':       lt.get('steals', 0),
        '阻攻':       lt.get('blocks', 0),
        '禁區得分':   g['paint'],
        '快攻得分':   g['fast_break'],
    })

labels_arr = np.array([s['won'] for s in game_team_stats])
P_all  = labels_arr.sum()
N_all  = (labels_arr == 0).sum()

def calc_roc(scores_arr, labels, higher_is_better=True):
    """計算 ROC 曲線、AUC、Youden's J 最佳切點"""
    if not higher_is_better:
        scores_arr = -scores_arr
    uniq = np.sort(np.unique(scores_arr))
    thresholds = np.concatenate([uniq - 0.001, uniq + 0.001])
    thresholds = np.sort(np.unique(thresholds))[::-1]

    P = labels.sum()
    N = (labels == 0).sum()
    pts = []
    for th in thresholds:
        pred = (scores_arr >= th).astype(int)
        tp = int(((pred == 1) & (labels == 1)).sum())
        fp = int(((pred == 1) & (labels == 0)).sum())
        tpr = tp / P if P else 0
        fpr = fp / N if N else 0
        pts.append((fpr, tpr, float(th if higher_is_better else -th)))

    pts = sorted(pts, key=lambda x: x[0])
    # 去重（同 fpr 取最高 tpr）
    dedup = {}
    for fpr, tpr, th in pts:
        key = round(fpr, 4)
        if key not in dedup or tpr > dedup[key][1]:
            dedup[key] = (fpr, tpr, th)
    pts = sorted(dedup.values(), key=lambda x: x[0])

    # AUC（梯形）
    auc_val = sum(
        (pts[i+1][0] - pts[i][0]) * (pts[i+1][1] + pts[i][1]) / 2
        for i in range(len(pts)-1)
    )

    # Youden's J = TPR - FPR，取最大
    best = max(pts, key=lambda x: x[1] - x[0])

    curve = [{'fpr': round(p[0], 4), 'tpr': round(p[1], 4)} for p in pts]
    return curve, round(auc_val, 4), {'fpr': round(best[0], 4), 'tpr': round(best[1], 4), 'threshold': best[2]}

# 定義預測指標（higher_is_better=False 代表數字越小越好，如失誤）
predictors = [
    ('三分命中率', '三分命中率', True),
    ('整體命中率', '整體命中率', True),
    ('阻攻',       '阻攻',       True),
    ('助攻',       '助攻',       True),
    ('失誤數',     '失誤數',     False),   # 失誤越少越好
    ('三分命中數', '三分命中數', True),
]

roc_results = {}
print('\n=== ROC 多指標分析 ===')
for label, key, higher in predictors:
    scores = np.array([s[key] for s in game_team_stats], dtype=float)
    curve, auc_val, best_pt = calc_roc(scores, labels_arr, higher)
    roc_results[label] = {
        'curve': curve,
        'auc':   auc_val,
        'best':  best_pt,
        'threshold': best_pt['threshold']
    }
    # 找最佳切點的原始值
    raw_vals = np.array([s[key] for s in game_team_stats], dtype=float)
    print(f'  {label}: AUC={auc_val:.3f}  最佳切點={best_pt["threshold"]:.1f}  (J={best_pt["tpr"]-best_pt["fpr"]:.3f})')

# ================================================================
# 9. 下一場勝率（從 schedule.json 動態讀取，若無則用備用值）
# ================================================================
_schedule_path = os.path.join(os.path.dirname(__file__), 'schedule.json')
if os.path.exists(_schedule_path):
    with open(_schedule_path, encoding='utf-8') as _f:
        _sched = json.load(_f)
    next_opp        = _sched['next_opponent']
    next_is_home    = _sched['next_is_home']
    next_date_label = _sched['next_date_label']
else:
    next_opp        = '新北中信特攻'
    next_is_home    = True
    next_date_label = '4/8（三）主場'
lion_wr_val  = float(win_rate)
opp_wr_val   = float(wr_arr[team_list.index(next_opp)])
next_prob_model = lion_wr_val / (lion_wr_val + opp_wr_val)

vs_next    = vs_record[next_opp]
hist_total = vs_next['w'] + vs_next['l']
hist_wr    = vs_next['w'] / hist_total if hist_total else 0.5
next_prob_base = 0.6 * next_prob_model + 0.4 * hist_wr
# 主客場調整（主場 +5%、客場 -5%）
next_prob_adj  = float(np.clip(next_prob_base + (HOME_ADV if next_is_home else -HOME_ADV), 0.05, 0.95))

print(f'\n下一場 vs {next_opp}（{next_date_label}）: 模型 {next_prob_model:.1%} / 加權 {next_prob_adj:.1%}')

# ================================================================
# 11. 四情境得分預測（依攻城獅綜合表現分四組）
# ================================================================
# 關鍵指標矩陣：3P%, TO, AST, FG%
feat_mat = np.array([
    [s['三分命中率'], s['失誤數'], s['助攻'], s['整體命中率']]
    for s in game_team_stats
], dtype=float)

lion_sc_arr = np.array([g['lion_score'] for g in games], dtype=float)
opp_sc_arr  = np.array([g['opp_score']  for g in games], dtype=float)
won_arr_all = np.array([g['won']         for g in games])

# Z-score 標準化（TO 取反：失誤越少越好）
mu_f  = feat_mat.mean(axis=0)
std_f = feat_mat.std(axis=0);  std_f[std_f < 1e-9] = 1e-9
z_f   = (feat_mat - mu_f) / std_f
z_f[:, 1] *= -1           # TO inverted
composite = z_f.mean(axis=1)

q25, q50, q75 = np.percentile(composite, [25, 50, 75])

# 每個分位數群的指標均值（作為情境說明）
def grp_stat_summary(mask, col, fmt=''):
    vals = feat_mat[mask, col]
    return f'{vals.mean():.{fmt}f}' if len(vals) else '—'

scenario_defs = [
    ('Best',  composite >= q75),
    ('Ideal', (composite >= q50) & (composite < q75)),
    ('Fair',  (composite >= q25) & (composite < q50)),
    ('Low',   composite < q25),
]

scenario_results = []
print('\n=== 四情境得分預測 ===')
for label, mask in scenario_defs:
    n = int(mask.sum())
    ls, os_ = lion_sc_arr[mask], opp_sc_arr[mask]
    wr = float(won_arr_all[mask].mean()) if n > 0 else 0
    grp = feat_mat[mask]
    stats_summary = {
        '3P%':  round(float(grp[:,0].mean()), 1) if n else 0,
        'TO':   round(float(grp[:,1].mean()), 1) if n else 0,
        'AST':  round(float(grp[:,2].mean()), 1) if n else 0,
        'FG%':  round(float(grp[:,3].mean()), 1) if n else 0,
    }
    print(f'  {label} (n={n}, WR={wr:.0%}): Lion {ls.mean():.1f}±{ls.std():.1f} '
          f'Opp {os_.mean():.1f}±{os_.std():.1f}  {stats_summary}')
    scenario_results.append({
        'label':      label,
        'n':          n,
        'win_rate':   round(wr, 3),
        'lion_mean':  round(float(ls.mean()), 1) if n else 0,
        'lion_std':   round(float(ls.std()),  1) if n else 0,
        'opp_mean':   round(float(os_.mean()), 1) if n else 0,
        'opp_std':    round(float(os_.std()),  1) if n else 0,
        'stats':      stats_summary,
    })

# ================================================================
# 12. Mann-Whitney U 顯著差異分析（勝 vs 敗）
# ================================================================
won_mw  = np.array([g['won'] for g in games])
mw_stats = {
    '三分命中率': np.array([s['三分命中率'] for s in game_team_stats], dtype=float),
    '三分命中數': np.array([s['三分命中數'] for s in game_team_stats], dtype=float),
    '整體命中率': np.array([s['整體命中率'] for s in game_team_stats], dtype=float),
    '失誤數':     np.array([s['失誤數']     for s in game_team_stats], dtype=float),
    '助攻':       np.array([s['助攻']       for s in game_team_stats], dtype=float),
    '籃板':       np.array([s['籃板']       for s in game_team_stats], dtype=float),
    '抄截':       np.array([s['抄截']       for s in game_team_stats], dtype=float),
    '阻攻':       np.array([s['阻攻']       for s in game_team_stats], dtype=float),
    '禁區得分':   np.array([s['禁區得分']   for s in game_team_stats], dtype=float),
    '快攻得分':   np.array([s['快攻得分']   for s in game_team_stats], dtype=float),
}

mann_results = []
print('\n=== Mann-Whitney U 顯著差異分析 ===')
for stat_name, values in mw_stats.items():
    w_vals = values[won_mw]
    l_vals = values[~won_mw]
    u_stat, p_val = sp_stats.mannwhitneyu(w_vals, l_vals, alternative='two-sided')
    n1, n2 = len(w_vals), len(l_vals)
    r = float(1 - 2 * u_stat / (n1 * n2))   # rank-biserial correlation
    sig = bool(p_val < 0.05)
    direction = 'W>L' if w_vals.mean() > l_vals.mean() else 'W<L'
    print(f'  {stat_name}: p={p_val:.4f}  r={r:+.3f}  {direction}  {"✓ 顯著" if sig else "ns"}')
    mann_results.append({
        'stat':          stat_name,
        'p_value':       round(float(p_val), 4),
        'effect_r':      round(r, 3),
        'significant':   sig,
        'wins_median':   round(float(np.median(w_vals)), 1),
        'losses_median': round(float(np.median(l_vals)), 1),
        'wins_mean':     round(float(w_vals.mean()), 1),
        'losses_mean':   round(float(l_vals.mean()), 1),
        'wins':          [round(float(v), 1) for v in w_vals],
        'losses':        [round(float(v), 1) for v in l_vals],
    })

sig_list = [r['stat'] for r in mann_results if r['significant']]
print(f'\n顯著指標（p<0.05）: {sig_list}')

# ================================================================
# 13. 主客場分析
# ================================================================
home_games_list = [g for g in games if g['is_home']]
away_games_list = [g for g in games if not g['is_home']]

def split_stats(gl):
    if not gl: return {}
    return {
        'gp':      len(gl),
        'wins':    sum(g['won'] for g in gl),
        'losses':  sum(not g['won'] for g in gl),
        'win_rate': round(sum(g['won'] for g in gl) / len(gl), 4),
        'avg_pts': mean([g['lion_score'] for g in gl]),
        'avg_opp': mean([g['opp_score']  for g in gl]),
        'net':     round(mean([g['lion_score'] for g in gl]) - mean([g['opp_score'] for g in gl]), 1),
    }

home_away_data = {
    'home': split_stats(home_games_list),
    'away': split_stats(away_games_list),
}
print(f'\n=== 主客場 ===')
print(f"主場 {home_away_data['home']['wins']}W{home_away_data['home']['losses']}L"
      f"  均得{home_away_data['home']['avg_pts']} 均失{home_away_data['home']['avg_opp']}")
print(f"客場 {home_away_data['away']['wins']}W{home_away_data['away']['losses']}L"
      f"  均得{home_away_data['away']['avg_pts']} 均失{home_away_data['away']['avg_opp']}")

# ================================================================
# 14. 節次分析
# ================================================================
quarter_data = {}
for q in [1, 2, 3, 4]:
    q_lion = [g['rounds'].get(q, 0) for g in games if q in g.get('rounds', {})]
    q_opp  = [g['opp_rounds'].get(q, 0) for g in games if q in g.get('opp_rounds', {})]
    pairs  = [(l, o) for l, o in zip(q_lion, q_opp)]
    q_wr   = round(sum(1 for l, o in pairs if l > o) / len(pairs), 4) if pairs else 0
    # 逐場節次數據（for chart）
    q_diffs = [round(l - o, 1) for l, o in pairs]
    quarter_data[f'Q{q}'] = {
        'avg_score': mean(q_lion),
        'avg_opp':   mean(q_opp),
        'win_rate':  q_wr,
        'games':     len(pairs),
        'diffs':     q_diffs,  # 每節得失分差（正=贏該節）
    }
    print(f"Q{q}: 均得{mean(q_lion)} 均失{mean(q_opp)} 節次勝率{q_wr:.1%}")

# ================================================================
# 10. 輸出 JSON
# ================================================================
output = {
    'meta': {'generated': __import__('datetime').date.today().isoformat(), 'total_games': lion_allgame_gp, 'games_remaining': games_remaining},
    'team_stats': {
        'wins': int(lion_total_wins), 'losses': int(lion_total_losses),
        'games_played': lion_allgame_gp, 'games_remaining': games_remaining,
        'avg_pts': avg_pts, 'avg_opp_pts': avg_opp_pts,
        'win_rate': round(float(win_rate), 4)
    },
    'standings': standings_sorted,
    'league_rtg': league_rtg,
    'games': games,
    'vs_summary': vs_summary,
    'heatmap': heatmap_data,
    'ppp_heatmap': ppp_heatmap_data,
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
    'roc': roc_results,
    'scenario_chart': scenario_results,
    'mann_whitney': mann_results,
    'next_game': {
        'opponent':          next_opp,
        'date':              next_date_label,
        'is_home':           next_is_home,
        'win_prob_model':    round(float(next_prob_model), 4),
        'win_prob_adjusted': round(float(next_prob_adj),   4),
        'historical_w':      int(vs_next['w']),
        'historical_l':      int(vs_next['l'])
    },
    'home_away':    home_away_data,
    'quarter_analysis': quarter_data,
}

out_path = os.path.join(os.path.dirname(__file__), 'processed_data.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f'\n>>> processed_data.json 輸出完成')
