#!/usr/bin/env python3
"""
scan_score 回測 v1
策略：每天對前200大市值股票計算 scan_score，
      進場條件：score >= ENTRY_SCORE
      出場條件：score <= EXIT_SCORE | 破MA60 | 外資連賣>=5 | 持有>MAX_HOLD | 停損>STOP_LOSS
進出場價格：用信號日收盤價（Point-in-time：當日收盤後才知道今天分數，明天才能交易，
            但台股散戶單實際可T+0 11:30前根據昨收大致估算，此處用昨收作保守估算）
成本模型：買 0.1425%+滑價0.05%；賣 0.1425%+0.3%證交稅+滑價0.05%
"""
import json, glob, os, math, statistics as st
from collections import defaultdict

# ─── 參數 ────────────────────────────────────────────────────────────────
ENTRY_SCORE = 10     # 進場門檻
EXIT_SCORE  = 6      # 出場（分數跌破）—— 從4→6，更快出場截斷後段虧損
MAX_HOLD    = 60     # 最長持有交易日 —— 從40→60，讓強勢倉位跑夠
STOP_LOSS   = -0.10  # 停損 -10% —— 從12%→10%，縮小單筆最大傷害
BUY_C   = 0.001425 + 0.0005    # 買進成本
SELL_C  = 0.001425 + 0.003 + 0.0005  # 賣出成本（含證交稅）
MAX_POS = 99         # 無上限（好的訊號全進，歷史統計每天通常1~2支）
BEAR_GATE = True     # bear regime 不進場（閘門控制）

# ─── 載入底層資料 ─────────────────────────────────────────────────────────
import sys; sys.path.insert(0, '.')
import backtest as B
import ls_loader as LS

days = B.days
print(f"回測期間: {days[0]} ~ {days[-1]}  ({len(days)} 交易日)")

# ─── 預載 t86（全部，不限120日）────────────────────────────────────────────
print("載入 t86...")
_t86 = {}
for fp in sorted(glob.glob('data/t86/*.json')):
    ds = os.path.basename(fp)[:-5]
    try:
        d = json.load(open(fp, encoding='utf-8'))
        row = {}
        for r in d.get('data', []):
            if r and len(r) > 18:
                try:
                    row[r[0]] = {
                        'f':    float(str(r[4]).replace(',','')),
                        'tr':   float(str(r[10]).replace(',','')),
                        'all3': float(str(r[18]).replace(',',''))
                    }
                except: pass
        _t86[ds] = row
    except: pass
_t86_dates = sorted(_t86)
print(f"  t86 載入 {len(_t86_dates)} 天")

# ─── 預載 margin（全部）──────────────────────────────────────────────────
print("載入 margin...")
_margin = {}
for fp in sorted(glob.glob('data/margin/*.json')):
    ds = os.path.basename(fp)[:-5]
    m, _ = LS.margin_day(ds)
    if m and len(m) > 100:
        _margin[ds] = m
_margin_dates = sorted(_margin)
print(f"  margin 載入 {len(_margin_dates)} 天")

# ─── 輔助函數 ─────────────────────────────────────────────────────────────
def _streak(t86_dates_slice, code, field):
    streak = 0; direction = None
    for ds in reversed(t86_dates_slice):
        r = _t86[ds].get(code)
        if r is None: break
        v = r.get(field)
        if v is None: break
        if direction is None:
            direction = 1 if v > 0 else (-1 if v < 0 else 0)
            if direction == 0: break
        if (direction == 1 and v > 0) or (direction == -1 and v < 0): streak += 1
        else: break
    return streak * direction if direction else 0

def _foreign_zscore(t86_dates_slice, code):
    vals = [_t86[ds][code]['f'] for ds in t86_dates_slice[-90:]
            if code in _t86.get(ds,{}) and _t86[ds][code].get('f') is not None]
    if len(vals) < 20: return None
    m = sum(vals)/len(vals)
    sd = (sum((v-m)**2 for v in vals)/len(vals))**.5
    if sd == 0: return None
    return (vals[-1]-m)/sd

def _margin_pressure(code, m_now, margin_hist_30):
    if not m_now or code not in m_now: return None, None, None, None
    fin, short = m_now[code]
    ratio = round(short/fin, 3) if fin > 0 else None
    hist_fin = [d[code][0] for d in margin_hist_30 if code in d]
    pctl = round(100*sum(1 for v in hist_fin if v < fin)/len(hist_fin)) if len(hist_fin) >= 5 else None
    return round(fin), round(short) if short else 0, ratio, pctl

def adj_ret(code, d0, d1):
    a = B.DD[d0]['stocks'].get(code, {}).get('close')
    b = B.DD[d1]['stocks'].get(code, {}).get('close')
    if not a or not b: return 0.0
    r = b/a - 1
    return 0.0 if abs(r) > 0.5 else r

# ─── scan_score（精簡版，只用每日可取得的資料）──────────────────────────
def compute_score(code, di, t86_window, m_now, margin_hist_30):
    """
    用 di 這天（含）及之前的資料計算分數。
    t86_window: 已篩到今日的 t86_dates 切片（最多120天）
    """
    s = B.DD[days[di]]['stocks'].get(code)
    if not s or not s.get('close'): return None, []

    px_full = [B.DD[days[k]]['stocks'].get(code, {}).get('close') for k in range(di+1)]
    px_full = [v for v in px_full if v]
    if len(px_full) < 61: return None, []

    close = px_full[-1]
    ma60  = sum(px_full[-60:])/60
    ma120 = sum(px_full[-120:])/120 if len(px_full) >= 120 else None

    # MA60 距離
    ma60_pct = (close/ma60 - 1)*100

    # 量能
    amounts = [B.DD[days[k]]['stocks'].get(code, {}).get('amount') or 0
               for k in range(max(0, di-19), di+1)]
    amounts = [v for v in amounts if v > 0]
    vol_ratio = (sum(amounts[-5:])/5) / (sum(amounts)/len(amounts)) if len(amounts) >= 20 else None

    # 外資連買/連賣
    fs = _streak(t86_window, code, 'f')
    ts = _streak(t86_window, code, 'tr')
    fz = _foreign_zscore(t86_window, code)

    # 融券比
    _, _, sr, fin_pctl = _margin_pressure(code, m_now, margin_hist_30)

    # 族群動能
    ind = B.co.get(code, {}).get('industry')
    nm = B.guess(ind) if ind else None
    sm = None
    if nm and di >= 21:
        c1 = B.DD[days[di]]['indices'].get(nm)
        c0 = B.DD[days[di-21]]['indices'].get(nm)
        if c1 and c0: sm = (c1/c0 - 1)*100

    # RSI
    def rsi14():
        if len(px_full) < 15: return 50
        g = l = 0
        for k in range(len(px_full)-14, len(px_full)):
            ch = px_full[k] - px_full[k-1]
            g += max(ch, 0); l += max(-ch, 0)
        return 100 if l == 0 else 100-100/(1+(g/14)/(l/14))

    rsi_v = rsi14()
    from_high = (close / max(px_full[-252:]) - 1)*100 if len(px_full) >= 252 else 0

    # 排雷
    riskscore = 0
    if close < ma60: riskscore -= 1
    if ma120 and close < ma120: riskscore -= 1
    ret60 = px_full[-1]/px_full[-61] - 1 if len(px_full) > 61 else None
    if ret60 is not None and ret60 < -0.1: riskscore -= 1
    if s.get('pe') is None: riskscore -= 1
    if sm is not None and sm < -3: riskscore -= 1
    if fs is not None and fs <= -3: riskscore -= 1
    if ts is not None and ts <= -3: riskscore -= 1
    if fin_pctl is not None and fin_pctl >= 90: riskscore -= 1

    # 評分（與 precompute.py scan_score v3 一致）
    pts = 0
    if sm is not None:
        if sm >= 1.5: pts += 3
        elif sm >= 0.5: pts += 2
        elif sm >= 0: pts += 1
        else: pts -= 2
    if ma60_pct >= 5: pts += 3
    elif ma60_pct >= 0: pts += 1
    else: pts -= 2
    if vol_ratio is not None:
        if vol_ratio >= 1.5: pts += 2
        elif vol_ratio >= 1.2: pts += 1
    if fs >= 5: pts += 2
    elif fs >= 3: pts += 1
    elif fs <= -5: pts -= 4
    elif fs <= -3: pts -= 3
    elif fs <= -1: pts -= 1
    if sr is not None:
        if sr >= 0.2: pts += 2
        elif sr >= 0.05: pts += 1
        elif sr == 0: pts -= 1
    if ts >= 3: pts += 1
    elif ts <= -3: pts -= 2
    elif ts <= -1: pts -= 1
    if fz is not None:
        if fz >= 2: pts += 1
        elif fz <= -2: pts -= 2
    if riskscore < 0: pts += riskscore * 2
    if 45 <= rsi_v <= 70: pts += 1
    elif rsi_v > 80: pts -= 1
    elif rsi_v < 35: pts -= 1
    if -10 <= from_high <= -2: pts += 1
    elif from_high < -20: pts -= 1

    return pts, {'ma60_pct': round(ma60_pct,1), 'sm': sm, 'fs': fs, 'ts': ts, 'sr': sr}

# ─── 建立前200大宇宙的快取（每天） ──────────────────────────────────────
mc = []
for code, s in B.DD[days[-1]]['stocks'].items():
    c = s['close']; sh = B.co.get(code, {}).get('shares')
    if c and sh and code.isdigit() and len(code) == 4:
        mc.append((c*sh, code))
mc.sort(reverse=True)
UNIVERSE = set(c for _, c in mc[:200])
print(f"宇宙 {len(UNIVERSE)} 檔")

# ─── 預計算每日 regime ───────────────────────────────────────────────────
_adj = [100.0]
for i in range(1, len(days)):
    _adj.append(_adj[-1]*(1+B.adj_ret('0050', days[i-1], days[i])))
def _ma(i, n): seg=_adj[max(0,i-n+1):i+1]; return sum(seg)/len(seg)
regime_map = {}
for i, d in enumerate(days):
    if i < 80: regime_map[d] = 'range'; continue
    r = _ma(i,60)/_ma(i-20,60) - 1
    regime_map[d] = 'bull' if r > 0.02 else 'bear' if r < -0.02 else 'range'

# ─── 主回測循環（固定 LOT 資金模型）───────────────────────────────────────
# 每筆固定 LOT_SIZE 元；現金不夠時追加注資，記錄累計成本曲線
LOT_SIZE = 100_000   # 每支固定 10 萬元

START_IDX = 120
portfolio = {}   # {code: {'entry_price','entry_di','entry_score','regime','lot'}}
results   = []

# 資金追蹤
cash           = LOT_SIZE          # 初始現金（夠第一筆）
total_invested = LOT_SIZE          # 累計注入成本
equity_curve   = []                # [{date, cash, invested, equity, ret_pct}]

print(f"\n開始回測: {days[START_IDX]} ~ {days[-1]}")
print(f"進場門檻={ENTRY_SCORE}分  出場門檻={EXIT_SCORE}分  最長持有={MAX_HOLD}日  停損={STOP_LOSS*100:.0f}%")
print(f"資金模式: 固定 {LOT_SIZE:,} 元/筆，現金不足自動注資\n")

for di in range(START_IDX, len(days)):
    d = days[di]

    t86_avail     = [x for x in _t86_dates if x <= d][-120:]
    m_dates_avail = [x for x in _margin_dates if x <= d]
    m_now         = _margin[m_dates_avail[-1]] if m_dates_avail else None
    margin_hist_30 = [_margin[x] for x in m_dates_avail[-30:] if x in _margin]

    # ── 出場 ──────────────────────────────────────────────────────────────
    to_exit = []
    for code, pos in portfolio.items():
        s = B.DD[d]['stocks'].get(code)
        if not s or not s.get('close'): continue
        cur_px = s['close']
        ret    = adj_ret(code, days[pos['entry_di']], d)
        score, _ = compute_score(code, di, t86_avail, m_now, margin_hist_30)

        reason = None
        if ret <= STOP_LOSS:
            reason = f'停損({ret*100:.1f}%)'
        elif score is not None and score <= EXIT_SCORE:
            reason = f'分數跌至{score}'
        elif di - pos['entry_di'] >= MAX_HOLD:
            reason = f'持有{MAX_HOLD}日到期'
        else:
            px_all = [B.DD[days[k]]['stocks'].get(code, {}).get('close') for k in range(di+1)]
            px_all = [v for v in px_all if v]
            if len(px_all) >= 60:
                ma60 = sum(px_all[-60:])/60
                if cur_px < ma60 * 0.98:
                    reason = f'破MA60({(cur_px/ma60-1)*100:.1f}%)'
            if not reason:
                fs = _streak(t86_avail, code, 'f')
                if fs <= -5:
                    reason = f'外資連賣{abs(fs)}日'
        if reason:
            to_exit.append((code, reason, cur_px, ret))

    for code, reason, cur_px, gross_ret in to_exit:
        pos     = portfolio.pop(code)
        net_ret = gross_ret - BUY_C - SELL_C
        lot     = pos['lot']
        net_twd = round(lot * net_ret)
        cash   += lot + net_twd          # 本金回收 + 損益
        results.append({
            'code': code,
            'name': B.co.get(code, {}).get('name', code),
            'entry_d': days[pos['entry_di']], 'exit_d': d,
            'entry_px': pos['entry_price'], 'exit_px': round(cur_px, 2),
            'gross_ret': round(gross_ret*100, 2),
            'net_ret':   round(net_ret*100, 2),
            'net_twd':   net_twd,
            'lot':       lot,
            'hold_days': di - pos['entry_di'],
            'reason': reason,
            'regime': pos.get('regime', 'range'),
            'entry_score': pos.get('entry_score'),
        })

    # ── 進場 ──────────────────────────────────────────────────────────────
    cur_regime = regime_map.get(d, 'range')
    if not (BEAR_GATE and cur_regime == 'bear'):
        candidates = []
        for code in UNIVERSE:
            if code in portfolio: continue
            score, meta = compute_score(code, di, t86_avail, m_now, margin_hist_30)
            if score is not None and score >= ENTRY_SCORE:
                candidates.append((score, code, meta))
        candidates.sort(reverse=True)
        for score, code, meta in candidates:
            entry_px = B.DD[d]['stocks'].get(code, {}).get('close')
            if not entry_px: continue
            if cash < LOT_SIZE:
                add = LOT_SIZE - cash
                cash += add
                total_invested += add
            cash -= LOT_SIZE
            portfolio[code] = {
                'entry_price': entry_px, 'entry_di': di,
                'entry_score': score, 'regime': cur_regime,
                'lot': LOT_SIZE,
            }

    # ── 每日淨值快照 ───────────────────────────────────────────────────────
    pos_val = sum(
        pos['lot'] * (1 + adj_ret(code, days[pos['entry_di']], d))
        for code, pos in portfolio.items()
    )
    equity_now = cash + pos_val
    ret_pct    = round((equity_now / total_invested - 1) * 100, 2)
    equity_curve.append({
        'date': d, 'cash': round(cash), 'invested': total_invested,
        'equity': round(equity_now), 'ret_pct': ret_pct,
    })

# ─── 強制平倉 ──────────────────────────────────────────────────────────────
di = len(days) - 1
d  = days[di]
t86_avail     = [x for x in _t86_dates if x <= d][-120:]
m_dates_avail = [x for x in _margin_dates if x <= d]
m_now         = _margin[m_dates_avail[-1]] if m_dates_avail else None
margin_hist_30 = [_margin[x] for x in m_dates_avail[-30:] if x in _margin]
for code, pos in list(portfolio.items()):
    cur_px    = B.DD[d]['stocks'].get(code, {}).get('close') or pos['entry_price']
    gross_ret = adj_ret(code, days[pos['entry_di']], d)
    net_ret   = gross_ret - BUY_C - SELL_C
    lot       = pos['lot']
    net_twd   = round(lot * net_ret)
    cash     += lot + net_twd
    results.append({
        'code': code,
        'name': B.co.get(code, {}).get('name', code),
        'entry_d': days[pos['entry_di']], 'exit_d': d,
        'entry_px': pos['entry_price'], 'exit_px': round(cur_px, 2),
        'gross_ret': round(gross_ret*100, 2),
        'net_ret':   round(net_ret*100, 2),
        'net_twd':   net_twd, 'lot': lot,
        'hold_days': di - pos['entry_di'],
        'reason': '回測結束',
        'regime': pos.get('regime', 'range'),
        'entry_score': pos.get('entry_score'),
    })

# ─── 統計 ────────────────────────────────────────────────────────────────
total_trades = len(results)
wins   = [r for r in results if r['net_ret'] > 0]
losses = [r for r in results if r['net_ret'] <= 0]
win_rate  = len(wins)/total_trades*100 if total_trades else 0
avg_win   = sum(r['net_ret'] for r in wins)/len(wins) if wins else 0
avg_loss  = sum(r['net_ret'] for r in losses)/len(losses) if losses else 0
avg_hold  = sum(r['hold_days'] for r in results)/total_trades if total_trades else 0
total_net_twd = sum(r.get('net_twd',0) for r in results)

# 從 equity_curve 提取序列做 MDD / 年化
eq_vals  = [e['equity']   for e in equity_curve]
inv_vals = [e['invested']  for e in equity_curve]
eq_dates = [e['date']      for e in equity_curve]

# 0050 benchmark（用倍數比較，起點 = 第一天 equity）
bm = [1.0]
for i in range(1, len(eq_dates)):
    bm.append(bm[-1] * (1 + B.adj_ret('0050', eq_dates[i-1], eq_dates[i])))

def mdd(series):
    peak = series[0]; worst = 0
    for v in series:
        if v > peak: peak = v
        dd = (v - peak) / peak
        if dd < worst: worst = dd
    return worst * 100

# equity_curve 的 MDD 用相對投入成本的帳戶曲線（倍數）
eq_mult = [eq_vals[i] / inv_vals[i] for i in range(len(eq_vals))]
strategy_mdd = mdd(eq_mult)
bm_mdd       = mdd(bm)

n_years  = len(eq_dates) / 252
ann_ret  = (eq_mult[-1] ** (1/n_years) - 1) * 100 if n_years > 0 else 0
bm_ann   = (bm[-1]      ** (1/n_years) - 1) * 100 if n_years > 0 else 0
total_return_pct = (eq_mult[-1] - 1) * 100

print("=" * 55)
print(f"  回測結果  scan_score ≥{ENTRY_SCORE} 進場 / ≤{EXIT_SCORE} 出場")
print("=" * 55)
print(f"  累計注入:  {total_invested:,.0f} 元")
print(f"  最終資產:  {eq_vals[-1]:,.0f} 元  現金={cash:,.0f}")
print(f"  總報酬:    {total_return_pct:+.1f}%（vs 投入成本）")
print(f"  總交易筆數: {total_trades}")
print(f"  勝率:       {win_rate:.1f}%  (勝{len(wins)} / 負{len(losses)})")
print(f"  平均獲利:  +{avg_win:.2f}%  平均虧損: {avg_loss:.2f}%")
print(f"  盈虧比:    {abs(avg_win/avg_loss):.2f}" if avg_loss != 0 else "  盈虧比: N/A")
print(f"  平均持有:  {avg_hold:.1f} 交易日")
print(f"  策略年化:  {ann_ret:+.1f}%   MDD: {strategy_mdd:.1f}%")
print(f"  0050 年化: {bm_ann:+.1f}%   MDD: {bm_mdd:.1f}%")
print(f"  超額年化:  {ann_ret-bm_ann:+.1f}%")
print()

# 出場原因統計
reason_counts = defaultdict(lambda: [0, 0, 0.0])
for r in results:
    key = r['reason'].split('(')[0][:8]
    reason_counts[key][0] += 1
    if r['net_ret'] > 0: reason_counts[key][1] += 1
    reason_counts[key][2] += r['net_ret']
print("出場原因分布:")
print(f"  {'原因':<10} {'次數':>5} {'勝率':>7} {'平均報酬':>9}")
for k, (cnt, w, tot) in sorted(reason_counts.items(), key=lambda x:-x[1][0]):
    print(f"  {k:<10} {cnt:>5}  {w/cnt*100:>6.1f}%  {tot/cnt:>+8.2f}%")
print()

# 年度統計
years = {}
for r in results:
    yr = r['entry_d'][:4]
    if yr not in years: years[yr] = []
    years[yr].append(r['net_ret'])
print("年度勝率:")
print(f"  {'年':>5} {'筆數':>5} {'勝率':>7} {'平均報酬':>9}")
for yr in sorted(years):
    rets = years[yr]
    wr  = sum(1 for x in rets if x > 0)/len(rets)*100
    avg = sum(rets)/len(rets)
    print(f"  {yr:>5} {len(rets):>5}  {wr:>6.1f}%  {avg:>+8.2f}%")
print()

# Regime 分層
print("Regime 分層:")
print(f"  {'Regime':<8} {'筆數':>5} {'勝率':>7} {'平均報酬':>9}")
regime_stats = defaultdict(list)
for r in results:
    regime_stats[r.get('regime', '?')].append(r['net_ret'])
for rg in ['bull', 'range', 'bear']:
    rets = regime_stats[rg]
    if not rets: print(f"  {rg:<8}     0  (無交易)"); continue
    wr  = sum(1 for x in rets if x > 0)/len(rets)*100
    avg = sum(rets)/len(rets)
    print(f"  {rg:<8} {len(rets):>5}  {wr:>6.1f}%  {avg:>+8.2f}%")

# 保存結果
output = {
    'params': {
        'entry_score': ENTRY_SCORE, 'exit_score': EXIT_SCORE,
        'max_hold': MAX_HOLD, 'stop_loss': STOP_LOSS,
        'lot_size': LOT_SIZE, 'bear_gate': BEAR_GATE,
    },
    'summary': {
        'total_trades': total_trades,
        'win_rate': round(win_rate, 1),
        'avg_win':  round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'avg_hold_days': round(avg_hold, 1),
        'ann_ret':     round(ann_ret, 1),
        'bm_ann_ret':  round(bm_ann, 1),
        'excess_ann':  round(ann_ret - bm_ann, 1),
        'total_return': round(total_return_pct, 1),
        'bm_total_return': round((bm[-1]-1)*100, 1),
        'strategy_mdd': round(strategy_mdd, 1),
        'bm_mdd':       round(bm_mdd, 1),
        'total_invested': total_invested,
        'final_equity':   round(eq_vals[-1]),
        'total_net_twd':  total_net_twd,
    },
    'regime_stats': {
        rg: {
            'n': len(rets),
            'win_rate': round(sum(1 for x in rets if x>0)/len(rets)*100, 1) if rets else 0,
            'avg_ret':  round(sum(rets)/len(rets), 2) if rets else 0,
        }
        for rg, rets in regime_stats.items()
    },
    'equity_curve': equity_curve,                         # 含 cash/invested/equity/ret_pct
    'bm': [[eq_dates[i], round(bm[i], 4)] for i in range(len(bm))],
    'trades': results,
}
json.dump(output, open('scan_bt_result.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(f"\n結果已存 scan_bt_result.json  ({total_trades} 筆交易)")
