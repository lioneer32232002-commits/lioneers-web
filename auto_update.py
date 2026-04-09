"""
auto_update.py - 新竹攻城獅賽後自動數據更新
排程在比賽日晚上 22:30 執行：
  爬取新比賽數據 → 更新球隊統計 → 重算分析 → 更新 OG 圖 → commit & push
"""
import json, os, sys, subprocess, re
from datetime import datetime, date, timedelta

# Windows 終端強制 UTF-8 輸出
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

try:
    import requests
except ImportError:
    print("缺少 requests 套件，正在安裝...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'requests'])
    import requests

# ──────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, 'data')
API_BASE  = 'https://api.tpbl.basketball/api'
LION_ID   = 4          # 新竹御嵿攻城獅 team id
DIVISION  = 9          # TPBL 聯盟 division id

ALLGAME_FILE  = os.path.join(DATA_DIR, '20260402_allgame.txt')
ALLTEAM_FILE  = os.path.join(DATA_DIR, 'allteam_latest.txt')
SCHEDULE_FILE = os.path.join(BASE_DIR, 'schedule.json')

EXCLUDE_FILES = {
    'lioneer_player.txt', 'lioneer.basic.txt',
    '20260330_allteam.txt', '20260402_allgame.txt',
    '20260402_allteam_update.txt', 'allteam_latest.txt',
}

WEEKDAY_CN = ['一', '二', '三', '四', '五', '六', '日']

# TPBL 七隊白名單（非這些隊伍的比賽不抓）
TPBL_TEAMS = {
    '新竹御嵿攻城獅', '桃園台啤永豐雲豹', '新北中信特攻',
    '福爾摩沙夢想家', '高雄全家海神', '臺北台新戰神', '新北國王'
}

TEAM_SHORT = {
    '新竹御嵿攻城獅': '攻城獅',
    '新北中信特攻':   '特攻',
    '桃園台啤永豐雲豹': '雲豹',
    '高雄鋼鐵人':     '鋼鐵人',
    '臺南台鋼獵鷹':   '獵鷹',
    '福爾摩沙夢想家': '夢想家',
    '富邦勇士':       '富邦',
}

# ──────────────────────────────────────────────
def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)

def api_get(path, timeout=20):
    url = f'{API_BASE}/{path}'
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()

# ── 1. 讀取本地賽程 ────────────────────────────
def load_schedule():
    with open(ALLGAME_FILE, encoding='utf-8') as f:
        return json.load(f)

def lion_games(schedule):
    return [g for g in schedule
            if g['home_team']['id'] == LION_ID or g['away_team']['id'] == LION_ID]

# ── 2. 找出哪些比賽還沒有本地數據 ──────────────
def existing_dates():
    dates = set()
    for fn in os.listdir(DATA_DIR):
        if fn.endswith('.txt') and fn not in EXCLUDE_FILES:
            d = fn.replace('.txt', '')
            if len(d) == 4:
                d = '2026' + d
            dates.add(d)
    return dates

# ── 3. 爬取新比賽統計 ──────────────────────────
def fetch_new_games(schedule):
    games = lion_games(schedule)
    existing = existing_dates()
    today = date.today()
    new_count = 0

    for g in sorted(games, key=lambda x: x['game_date']):
        game_date = datetime.strptime(g['game_date'], '%Y-%m-%d').date()
        date_key  = g['game_date'].replace('-', '')

        # 只抓過去的、還沒有數據的比賽
        if game_date > today:
            continue
        if date_key in existing:
            continue

        log(f"嘗試爬取: {g['game_date']} (id={g['id']})...")
        try:
            stats = api_get(f"games/{g['id']}/stats")
            # 確認是 dict 格式（list 代表比賽未開始/無數據）
            if not isinstance(stats, dict):
                log(f"  → 比賽數據格式異常，跳過")
                continue
            # 確認對手是 TPBL 七隊之一（過濾非正規賽）
            opp_id = g['away_team']['id'] if g['home_team']['id'] == LION_ID else g['home_team']['id']
            opp_name_check = (stats.get('home_team') or stats.get('away_team') or {}).get('name', '')
            home_name = stats.get('home_team', {}).get('name', '')
            away_name = stats.get('away_team', {}).get('name', '')
            both_names = {home_name, away_name}
            if not both_names.issubset(TPBL_TEAMS | {''}):
                log(f"  → 非 TPBL 正規賽（{both_names - TPBL_TEAMS}），跳過")
                continue
            # 確認有得分（比賽已完成）
            ht = stats.get('home_team', {})
            ht_total = ht.get('teams', {}).get('total', {})
            if not ht_total.get('won_score') and not ht_total.get('lost_score'):
                log(f"  → 比賽尚未結束或數據未更新，跳過")
                continue
            out = os.path.join(DATA_DIR, f"{date_key}.txt")
            with open(out, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            log(f"  → 已儲存 {out}")
            new_count += 1
        except Exception as e:
            log(f"  → 爬取失敗: {e}")

    return new_count

# ── 4. 更新聯盟球隊統計 ────────────────────────
def update_team_stats():
    log("更新聯盟球隊統計...")
    try:
        data = api_get(f"games/stats/teams?division_id={DIVISION}")
        with open(ALLTEAM_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log(f"  → 已更新 allteam_latest.txt")
        return True
    except Exception as e:
        log(f"  → 球隊統計更新失敗: {e}")
        return False

# ── 5. 計算下一場比賽資訊並寫入 schedule.json ──
def update_schedule(schedule):
    games = lion_games(schedule)
    today = date.today()
    already_played = existing_dates()   # 有本地檔案 = 已取得數據 = 已打完

    # 今天（含）之後、且還沒有本地數據的比賽 = 尚未打完
    upcoming = sorted(
        [g for g in games
         if datetime.strptime(g['game_date'], '%Y-%m-%d').date() >= today
         and g['game_date'].replace('-', '') not in already_played],
        key=lambda x: x['game_date']
    )

    if not upcoming:
        log("賽季結束，沒有下一場比賽")
        # 清除 schedule.json
        if os.path.exists(SCHEDULE_FILE):
            os.remove(SCHEDULE_FILE)
        return None

    g = upcoming[0]
    is_home  = g['home_team']['id'] == LION_ID
    opp_team = g['away_team'] if is_home else g['home_team']
    opp_name = opp_team['name']

    dt = datetime.strptime(g['game_date'], '%Y-%m-%d')
    wd = WEEKDAY_CN[dt.weekday()]
    ha = '主場' if is_home else '客場'
    date_label = f"{dt.month}/{dt.day}（{wd}）{ha}"

    sched = {
        'next_opponent':   opp_name,
        'next_is_home':    is_home,
        'next_date_label': date_label,
        'next_game_date':  g['game_date'],
        'next_game_id':    g['id'],
    }
    with open(SCHEDULE_FILE, 'w', encoding='utf-8') as f:
        json.dump(sched, f, ensure_ascii=False, indent=2)
    log(f"  → 下一場: {date_label} vs {opp_name}")
    return sched

# ── 6. 執行 process_data.py ────────────────────
def run_process_data():
    log("執行 process_data.py...")
    log_path = os.path.join(BASE_DIR, 'auto_update.log')
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    with open(log_path, 'w', encoding='utf-8') as logf:
        result = subprocess.run(
            [sys.executable, os.path.join(BASE_DIR, 'process_data.py')],
            stdout=logf, stderr=logf, cwd=BASE_DIR, env=env
        )
    if result.returncode != 0:
        with open(log_path, encoding='utf-8', errors='replace') as logf:
            tail = logf.read()[-600:]
        print(f"  [ERROR] process_data.py 失敗:\n{tail}", flush=True)
        return False
    log("  → process_data.py 完成")
    return True

# ── 7. 更新 index.html 的 og:description + 版號 ─
def update_og_meta(next_info):
    html_path = os.path.join(BASE_DIR, 'index.html')
    json_path = os.path.join(BASE_DIR, 'processed_data.json')

    with open(json_path, encoding='utf-8') as f:
        pd = json.load(f)
    with open(html_path, encoding='utf-8') as f:
        src = f.read()

    # 組描述文字
    ts      = pd.get('team_stats', {})
    wins    = ts.get('wins', '?')
    losses  = ts.get('losses', '?')
    sim     = pd.get('simulation', {})
    prob_po = int(sim.get('prob_playoff', 0) * 100)
    prob_ch = int(sim.get('prob_champ', 0) * 100)

    if next_info:
        opp_short = TEAM_SHORT.get(next_info['next_opponent'], next_info['next_opponent'])
        ha = '主場' if next_info['next_is_home'] else '客場'
        desc = (f"新竹攻城獅 2025-26｜{wins}勝{losses}敗・"
                f"進季後賽 {prob_po}%・奪冠 {prob_ch}%・"
                f"下一場 vs {opp_short}（{ha}）")
    else:
        desc = f"新竹攻城獅 2025-26｜{wins}勝{losses}敗・進季後賽 {prob_po}%・奪冠 {prob_ch}%"

    # 替換 og:description 和 description
    src = re.sub(
        r'(<meta[^>]*name="description"[^>]*content=")[^"]*(")',
        f'\\1{desc}\\2', src
    )
    src = re.sub(
        r'(<meta[^>]*property="og:description"[^>]*content=")[^"]*(")',
        f'\\1{desc}\\2', src
    )
    # og:image 版號 +1
    src = re.sub(
        r'(og-image\.png\?v=)(\d+)',
        lambda m: m.group(1) + str(int(m.group(2)) + 1),
        src
    )

    # footer 數據更新日期（取最後一場比賽日期）
    last_game = pd.get('games', [{}])[-1].get('date', '')
    if last_game:
        display_date = f"{last_game[:4]}/{last_game[4:6]}/{last_game[6:]}" if len(last_game) == 8 else last_game.replace('-', '/')
        src = re.sub(r'數據更新至 \d{4}/\d{2}/\d{2}', f'數據更新至 {display_date}', src)

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(src)
    log(f"  → og:description 更新完成")

# ── 8. 產生 OG 圖片 ────────────────────────────
def generate_og():
    log("產生 og-image.png...")
    # 嘗試常見的 node 路徑
    node_candidates = ['node', r'C:\Program Files\nodejs\node.exe',
                       r'C:\Program Files (x86)\nodejs\node.exe']
    node_cmd = None
    for nc in node_candidates:
        try:
            r = subprocess.run([nc, '--version'], capture_output=True, timeout=5)
            if r.returncode == 0:
                node_cmd = nc
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    if not node_cmd:
        log("  → 找不到 node.js，跳過 OG 圖片產生（不影響數據更新）")
        return
    try:
        result = subprocess.run(
            [node_cmd, os.path.join(BASE_DIR, 'generate-og.js')],
            capture_output=True, text=True, cwd=BASE_DIR, timeout=30
        )
        if result.returncode != 0:
            log(f"  → OG 圖片產生失敗（不影響數據更新）: {result.stderr[:200]}")
        else:
            log("  → og-image.png 產生完成")
    except Exception as e:
        log(f"  → OG 圖片產生略過: {e}")

# ── 9. Git commit + push ───────────────────────
def git_push(new_count, next_info):
    today_str = date.today().isoformat()

    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'

    def run_git(cmd):
        return subprocess.run(
            cmd, cwd=BASE_DIR, capture_output=True,
            text=True, encoding='utf-8', errors='replace',
            shell=True, env=env
        )

    run_git('git add processed_data.json index.html process_data.py og-image.png schedule.json')
    run_git('git add data/')

    opp = next_info['next_opponent'] if next_info else 'TBD'
    msg = f"Auto-update {today_str}: +{new_count} game(s), next={opp}"
    result = run_git(f'git commit -m "{msg}"')

    stdout = (result.stdout or '') + (result.stderr or '')
    if 'nothing to commit' in stdout:
        log("沒有變更，不需要 commit")
        return

    run_git('git pull --rebase origin main')
    push = run_git('git push origin main')
    if push.returncode == 0:
        log(f"  → ✅ 推送成功！{msg}")
    else:
        log(f"  → ❌ Push 失敗: {push.stderr[:300]}")

# ── MAIN ──────────────────────────────────────
if __name__ == '__main__':
    log("=" * 50)
    log("攻城獅自動更新開始")
    log("=" * 50)

    schedule = load_schedule()

    # 爬新比賽
    new_count = fetch_new_games(schedule)
    log(f"新比賽數: {new_count}")

    # 更新球隊統計
    update_team_stats()

    # 計算下一場
    next_info = update_schedule(schedule)

    # 重算分析
    if not run_process_data():
        log("process_data.py 失敗，中止更新")
        sys.exit(1)

    # 更新 OG meta
    update_og_meta(next_info)

    # 產生 OG 圖片（可選，需要 node）
    generate_og()

    # Git 推送
    git_push(new_count, next_info)

    log("=" * 50)
    log("自動更新完成")
    log("=" * 50)
