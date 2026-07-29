#!/usr/bin/env python3
"""
止損敏感度比較：-10% vs -7%
重用 scan_backtest 的資料與評分函數，只換 STOP_LOSS 參數。
同時追蹤「誤殺」：停損出場後 N 日內股價回到進場價以上。
"""
import json, glob, os, sys
from collections import defaultdict
sys.path.insert(0, '.')

# ── 直接 import scan_backtest 裡的所有預算資料 ──────────────────────────
# 為了不重跑 600MB 資料，把 scan_backtest.py 拆的核心直接 import
import backtest as B
import ls_loader as LS

ENTRY_SCORE = 10
EXIT_SCORE  = 6
MAX_HOLD    = 60
BUY_C       = 0.001425 + 0.0005
SELL_C      = 0.001425 + 0.003 + 0.0005
LOT_SIZE    = 100_000

# ── 預載 t86 ───────────────────────────────────────────────────────────────
print("載入資料...")
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
                        'f':  float(str(r[4]).replace(',','')),
                        'tr': float(str(r[10]).replace(',','')),
                    }
                except: pass
        _t86[ds] = row
    except: pass
_t86_dates = sorted(_t86)

_margin = {}
for fp in sorted(glob.glob('data/margin/*.json')):
    ds = os.path.basename(fp)[:-5]
    m, _ = LS.margin_day(ds)
    if m and len(m) > 100:
        _margin[ds] = m
_margin_dates = sorted(_margin)

days = B.days
print(f"  {len(days)} 交易日  t86={len(_t86_dates)}  margin={len(_margin_dates)}")

# ── 工具函數 ───────────────────────────────────────────────────────────────
def _streak(window, code, field):
    streak = 0; direction = None
    for ds in reversed(window):
        r = _t86[ds].get(code)
        if not r: break
        v = r.get(field)
        if v is None: break
        if direction is None:
            direction = 1 if v > 0 else (-1 if v < 0 else 0)
            if direction == 0: break
        if (direction==1 and v>0) or (direction==-1 and v<0): streak += 1
        else: break
    return streak * direction if direction else 0

def _fz(window, code):
    vals = [_t86[ds][code]['f'] for ds in window[-90:]
            if code in _t86.get(ds,{}) and _t86[ds][code].get('f') is not None]
    if len(vals) < 20: return None
    m = sum(vals)/len(vals)
    sd = (sum((v-m)**2 for v in vals)/len(vals))**.5
    return None if sd==0 else (vals[-1]-m)/sd

def adj_ret(code, d0, d1):
    a = B.DD[d0]['stocks'].get(code,{}).get('close')
    b = B.DD[d1]['stocks'].get(code,{}).get('close')
    if not a or not b: return 0.0
    r = b/a - 1
    return 0.0 if abs(r) > 0.5 else r

def compute_score(code, di, t86w, m_now, mh30):
    s = B.DD[days[di]]['stocks'].get(code)
    if not s or not s.get('close'): return None
    px = [B.DD[days[k]]['stocks'].get(code,{}).get('close') for k in range(di+1)]
    px = [v for v in px if v]
    if len(px) < 61: return None
    close = px[-1]; ma60 = sum(px[-60:])/60
    ma120 = sum(px[-120:])/120 if len(px)>=120 else None
    ma60_pct = (close/ma60-1)*100
    amounts = [B.DD[days[k]]['stocks'].get(code,{}).get('amount') or 0
               for k in range(max(0,di-19), di+1)]
    amounts = [v for v in amounts if v>0]
    vol_ratio = (sum(amounts[-5:])/5)/(sum(amounts)/len(amounts)) if len(amounts)>=20 else None
    fs = _streak(t86w, code, 'f')
    ts = _streak(t86w, code, 'tr')
    fz = _fz(t86w, code)
    _, sr = (lambda m: (m.get(code,(None,None)) if m else (None,None)))(m_now), None
    if m_now and code in m_now:
        fin, short = m_now[code]
        sr = round(short/fin,3) if fin>0 else None
    fin_pctl = None
    if mh30 and m_now and code in m_now:
        fin = m_now[code][0]
        hist = [d[code][0] for d in mh30 if code in d]
        fin_pctl = round(100*sum(1 for v in hist if v<fin)/len(hist)) if len(hist)>=5 else None
    ind = B.co.get(code,{}).get('industry')
    nm = B.guess(ind) if ind else None
    sm = None
    if nm and di>=21:
        c1=B.DD[days[di]]['indices'].get(nm)
        c0=B.DD[days[di-21]]['indices'].get(nm)
        if c1 and c0: sm=(c1/c0-1)*100
    def rsi14():
        if len(px)<15: return 50
        g=l=0
        for k in range(len(px)-14,len(px)):
            ch=px[k]-px[k-1]; g+=max(ch,0); l+=max(-ch,0)
        return 100 if l==0 else 100-100/(1+(g/14)/(l/14))
    rsi_v = rsi14()
    from_high = (close/max(px[-252:])-1)*100 if len(px)>=252 else 0
    riskscore=0
    if close<ma60: riskscore-=1
    if ma120 and close<ma120: riskscore-=1
    ret60 = px[-1]/px[-61]-1 if len(px)>61 else None
    if ret60 is not None and ret60<-0.1: riskscore-=1
    if s.get('pe') is None: riskscore-=1
    if sm is not None and sm<-3: riskscore-=1
    if fs<=- 3: riskscore-=1
    if ts<=-3: riskscore-=1
    if fin_pctl is not None and fin_pctl>=90: riskscore-=1
    pts=0
    if sm is not None:
        if sm>=1.5: pts+=3
        elif sm>=0.5: pts+=2
        elif sm>=0: pts+=1
        else: pts-=2
    if ma60_pct>=5: pts+=3
    elif ma60_pct>=0: pts+=1
    else: pts-=2
    if vol_ratio is not None:
        if vol_ratio>=1.5: pts+=2
        elif vol_ratio>=1.2: pts+=1
    if fs>=5: pts+=2
    elif fs>=3: pts+=1
    elif fs<=-5: pts-=4
    elif fs<=-3: pts-=3
    elif fs<=-1: pts-=1
    if sr is not None:
        if sr>=0.2: pts+=2
        elif sr>=0.05: pts+=1
        elif sr==0: pts-=1
    if ts>=3: pts+=1
    elif ts<=-3: pts-=2
    elif ts<=-1: pts-=1
    if fz is not None:
        if fz>=2: pts+=1
        elif fz<=-2: pts-=2
    if riskscore<0: pts+=riskscore*2
    if 45<=rsi_v<=70: pts+=1
    elif rsi_v>80: pts-=1
    elif rsi_v<35: pts-=1
    if -10<=from_high<=-2: pts+=1
    elif from_high<-20: pts-=1
    return pts

# ── 宇宙 & Regime ──────────────────────────────────────────────────────────
mc=[]
for code,s in B.DD[days[-1]]['stocks'].items():
    c=s['close']; sh=B.co.get(code,{}).get('shares')
    if c and sh and code.isdigit() and len(code)==4: mc.append((c*sh,code))
mc.sort(reverse=True)
UNIVERSE=set(c for _,c in mc[:200])

_adj=[100.0]
for i in range(1,len(days)):
    _adj.append(_adj[-1]*(1+B.adj_ret('0050',days[i-1],days[i])))
def _ma(i,n): seg=_adj[max(0,i-n+1):i+1]; return sum(seg)/len(seg)
regime_map={}
for i,d in enumerate(days):
    if i<80: regime_map[d]='range'; continue
    r=_ma(i,60)/_ma(i-20,60)-1
    regime_map[d]='bull' if r>0.02 else 'bear' if r<-0.02 else 'range'

# ── 回測主函數 ────────────────────────────────────────────────────────────
def run_bt(stop_loss, label):
    portfolio={}; results=[]; cash=LOT_SIZE; total_inv=LOT_SIZE
    START_IDX=120
    for di in range(START_IDX, len(days)):
        d=days[di]
        t86w=[x for x in _t86_dates if x<=d][-120:]
        mda=[x for x in _margin_dates if x<=d]
        m_now=_margin[mda[-1]] if mda else None
        mh30=[_margin[x] for x in mda[-30:] if x in _margin]

        # 出場
        to_exit=[]
        for code,pos in portfolio.items():
            s=B.DD[d]['stocks'].get(code)
            if not s or not s.get('close'): continue
            cur_px=s['close']
            ret=adj_ret(code, days[pos['entry_di']], d)
            score=compute_score(code, di, t86w, m_now, mh30)
            reason=None
            if ret<=stop_loss:
                reason=f'停損({ret*100:.1f}%)'
            elif score is not None and score<=EXIT_SCORE:
                reason=f'分數跌至{score}'
            elif di-pos['entry_di']>=MAX_HOLD:
                reason=f'持有到期'
            else:
                px_all=[B.DD[days[k]]['stocks'].get(code,{}).get('close') for k in range(di+1)]
                px_all=[v for v in px_all if v]
                if len(px_all)>=60:
                    ma60=sum(px_all[-60:])/60
                    if cur_px<ma60*0.98: reason=f'破MA60'
                if not reason and _streak(t86w,code,'f')<=-5: reason=f'外資連賣'
            if reason: to_exit.append((code,reason,cur_px,ret,di))

        for code,reason,cur_px,gross,exit_di in to_exit:
            pos=portfolio.pop(code)
            net=gross-BUY_C-SELL_C
            lot=pos['lot']
            cash+=lot+round(lot*net)
            results.append({
                'code':code,
                'entry_d':days[pos['entry_di']],'exit_d':d,
                'entry_px':pos['entry_px'],'exit_px':cur_px,
                'entry_di':pos['entry_di'],'exit_di':exit_di,
                'gross_ret':round(gross*100,2),
                'net_ret':round(net*100,2),
                'reason':reason,
                'regime':pos.get('regime','range'),
            })

        # 進場
        cur_rg=regime_map.get(d,'range')
        if not (cur_rg=='bear'):
            cands=[]
            for code in UNIVERSE:
                if code in portfolio: continue
                sc=compute_score(code,di,t86w,m_now,mh30)
                if sc is not None and sc>=ENTRY_SCORE: cands.append((sc,code))
            cands.sort(reverse=True)
            for sc,code in cands:
                epx=B.DD[d]['stocks'].get(code,{}).get('close')
                if not epx: continue
                if cash<LOT_SIZE:
                    add=LOT_SIZE-cash; cash+=add; total_inv+=add
                cash-=LOT_SIZE
                portfolio[code]={'entry_px':epx,'entry_di':di,
                                 'regime':cur_rg,'lot':LOT_SIZE}

    # 強制平倉
    di=len(days)-1; d=days[di]
    for code,pos in list(portfolio.items()):
        cur_px=B.DD[d]['stocks'].get(code,{}).get('close') or pos['entry_px']
        gross=adj_ret(code,days[pos['entry_di']],d)
        net=gross-BUY_C-SELL_C
        results.append({
            'code':code,'entry_d':days[pos['entry_di']],'exit_d':d,
            'entry_px':pos['entry_px'],'exit_px':cur_px,
            'entry_di':pos['entry_di'],'exit_di':di,
            'gross_ret':round(gross*100,2),'net_ret':round(net*100,2),
            'reason':'回測結束','regime':pos.get('regime','range'),
        })
        cash+=pos['lot']+round(pos['lot']*net)

    return results, cash, total_inv

# ── 跑兩組 ─────────────────────────────────────────────────────────────────
print("\n跑 -10% 止損...")
r10, cash10, inv10 = run_bt(-0.10, '-10%')
print("跑 -7% 止損...")
r7,  cash7,  inv7  = run_bt(-0.07, '-7%')

# ── 誤殺分析（停損後 30 日內收復進場價） ────────────────────────────────
def false_kills(results, stop_loss_label):
    stopped = [r for r in results if r['reason'].startswith('停損')]
    fk = []
    for r in stopped:
        exit_di = r['exit_di']
        entry_px = r['entry_px']
        code = r['code']
        # 出場後 30 交易日內逐日看
        recovered = False
        recovery_days = None
        for fwd in range(1, 31):
            future_di = exit_di + fwd
            if future_di >= len(days): break
            future_d = days[future_di]
            fut_px = B.DD[future_d]['stocks'].get(code,{}).get('close')
            if fut_px and fut_px >= entry_px:
                recovered = True
                recovery_days = fwd
                break
        fk.append({**r, 'recovered': recovered, 'recovery_days': recovery_days})
    return fk

fk10 = false_kills(r10, '-10%')
fk7  = false_kills(r7,  '-7%')

# ── 統計 ──────────────────────────────────────────────────────────────────
def stats(results):
    n = len(results)
    wins = [r for r in results if r['net_ret']>0]
    losses = [r for r in results if r['net_ret']<=0]
    stops = [r for r in results if r['reason'].startswith('停損')]
    wr = len(wins)/n*100 if n else 0
    aw = sum(r['net_ret'] for r in wins)/len(wins) if wins else 0
    al = sum(r['net_ret'] for r in losses)/len(losses) if losses else 0
    return n, wr, aw, al, len(stops)

n10,wr10,aw10,al10,ns10 = stats(r10)
n7, wr7, al7_,aw7_, ns7 = stats(r7)  # recompute cleanly
wins7=[r for r in r7 if r['net_ret']>0]; losses7=[r for r in r7 if r['net_ret']<=0]
wr7=len(wins7)/n7*100; aw7=sum(r['net_ret'] for r in wins7)/len(wins7) if wins7 else 0
al7=sum(r['net_ret'] for r in losses7)/len(losses7) if losses7 else 0

fk10_yes = sum(1 for x in fk10 if x['recovered'])
fk7_yes  = sum(1 for x in fk7  if x['recovered'])

print()
print("="*60)
print(f"  {'指標':<18} {'止損 -10%':>14} {'止損 -7%':>14}")
print("="*60)
print(f"  {'總交易筆數':<18} {n10:>14,} {n7:>14,}")
print(f"  {'停損觸發次數':<18} {ns10:>14} {ns7:>14}")
print(f"  {'勝率':<18} {wr10:>13.1f}% {wr7:>13.1f}%")
print(f"  {'平均獲利':<18} {aw10:>13.2f}% {aw7:>13.2f}%")
print(f"  {'平均虧損':<18} {al10:>13.2f}% {al7:>13.2f}%")
if al10 and al7:
    print(f"  {'盈虧比':<18} {abs(aw10/al10):>14.2f} {abs(aw7/al7):>14.2f}")
print(f"  {'最終資產(萬)':<18} {cash10/10000:>13.1f} {cash7/10000:>13.1f}")
print(f"  {'累計投入(萬)':<18} {inv10/10000:>13.1f} {inv7/10000:>13.1f}")
print(f"  {'總報酬率':<18} {(cash10/inv10-1)*100:>13.1f}% {(cash7/inv7-1)*100:>13.1f}%")
print()
print(f"  ── 誤殺分析（停損後30日內收復進場價）──")
print(f"  {'停損總次數':<18} {ns10:>14} {ns7:>14}")
print(f"  {'其中誤殺':<18} {fk10_yes:>13} ({fk10_yes/ns10*100:.0f}%) {fk7_yes:>6} ({fk7_yes/ns7*100:.0f}%)" if ns10 and ns7 else "")
print(f"  {'未誤殺（真壞）':<18} {ns10-fk10_yes:>13} ({(ns10-fk10_yes)/ns10*100:.0f}%) {ns7-fk7_yes:>5} ({(ns7-fk7_yes)/ns7*100:.0f}%)" if ns10 and ns7 else "")
print()

# 誤殺明細（-7% 版）
if fk7:
    print(f"  ── -7% 誤殺明細（{fk7_yes} 筆收復，{ns7-fk7_yes} 筆真壞）──")
    print(f"  {'代號':<6} {'進場':>10} {'出場':>10} {'出場報酬':>9} {'收復?':>5} {'天數':>5}")
    for x in sorted(fk7, key=lambda r: r['entry_d']):
        rec = f"{x['recovery_days']}日後" if x['recovered'] else '未收復'
        print(f"  {x['code']:<6} {x['entry_d']:>10} {x['exit_d']:>10} {x['net_ret']:>+8.2f}% {str(x['recovered']):>5} {rec:>6}")
