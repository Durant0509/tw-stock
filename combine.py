#!/usr/bin/env python3
"""路A: 动能引擎 + 熊市防御, 能否把 MDD -58% 压下来又保住报酬?
P7 地板: 必须赢过「纯动能引擎 passive」才算数 (不是赢 0050)。
R20 警告: regime 减码常是负贡献, 预期可能失败, 让数据说话。

三个 regime 训练组 (用 0050 MA60 斜率, 当下可得, 无 look-ahead):
  V1 纯动能引擎 (地板)
  V2 熊市切撿便宜 (bear regime 时选股改用低PE)
  V3 熊市减码 (bear regime 时仓位砍半, 现金避险)
"""
import math, random
import statistics as st
import backtest as B
from validation import daily_returns, mdd_from_rets, sharpe, skew_kurt, norm_cdf, norm_ppf
random.seed(42)
days=B.days

# regime: 0050 MA60 斜率 (分割调整), 当下判定
adj=[]; v=100.0
for i,d in enumerate(days):
    if i>0: v*=(1+B.adj_ret('0050',days[i-1],d))
    adj.append(v)
def ma(i): seg=adj[max(0,i-60+1):i+1]; return sum(seg)/len(seg)
def regime_at(d):
    i=days.index(d)
    if i<80: return 'warmup'
    slope=ma(i)/ma(i-20)-1
    return 'bull' if slope>0.02 else 'bear' if slope<-0.02 else 'range'

def run_combo(mode):
    """mode: 'engine'=纯动能 / 'switch'=熊切撿便宜 / 'decut'=熊减码半仓"""
    start=80; cash=1.0; pos={}; curve=[]; trades=0
    rebal=set(days[start::B.STEP])
    for i in range(start,len(days)):
        d=days[i]; dp=days[i-1]; reg=regime_at(d)
        for code in list(pos):
            pos[code]['val']*=(1+B.adj_ret(code,dp,d))
            c=B.cl(code,d)
            if c and pos[code]['entry'] and c/pos[code]['entry']-1<=B.STOP:
                cash+=pos[code]['val']*(1-B.SELL_C); trades+=1; del pos[code]
        if d in rebal:
            # 选股逻辑依 mode + regime
            if mode=='switch' and reg=='bear':
                cand=B.candidates(d)          # 熊市改用撿便宜(含低PE抗跌)
            else:
                cand=B.candidates_ma60only(d) # 其余用纯动能
            if cand:
                wv,wm=(0.5,0.5) if (mode=='switch' and reg=='bear') else (0.0,1.0)
                scored=sorted(cand,key=lambda c:wv*cand[c][0]+wm*cand[c][1],reverse=True)
                target=set(scored[:B.N])
                total=cash+sum(p['val'] for p in pos.values())
                # decut 模式熊市只投一半, 其余现金
                invest_frac=0.5 if (mode=='decut' and reg=='bear') else 1.0
                each=(total*invest_frac)/B.N
                for code in list(pos):
                    if code not in target: cash+=pos[code]['val']*(1-B.SELL_C); trades+=1; del pos[code]
                for code in target:
                    cur=pos.get(code,{}).get('val',0); delta=each-cur
                    if delta>0:
                        buy=min(delta,cash); cash-=buy
                        if code in pos: pos[code]['val']+=buy*(1-B.BUY_C)
                        else: pos[code]={'val':buy*(1-B.BUY_C),'entry':B.cl(code,d)}; trades+=1
                    elif delta<-1e-9: pos[code]['val']+=delta; cash-=delta*(1-B.SELL_C)
        curve.append((d,cash+sum(p['val'] for p in pos.values())))
    return curve,trades

def stats(curve):
    vals=[v for _,v in curve]
    tot=vals[-1]/vals[0]-1; yrs=len(vals)/252; cagr=vals[-1]**(1/yrs)-1
    peak=vals[0]; mdd=0
    for v in vals: peak=max(peak,v); mdd=min(mdd,v/peak-1)
    return tot,cagr,mdd,cagr/abs(mdd) if mdd else 0

variants={}
for mode,label in [('engine','V1纯动能(地板)'),('switch','V2熊切撿便宜'),('decut','V3熊减码半仓')]:
    print(f"跑 {label}...")
    variants[label]=run_combo(mode)

z=B.bench_0050()
print(f"\n=== 路A: 动能引擎 + 熊市防御 ({days[80]}~{days[-1]}) ===")
print(f"{'变体':<18}{'总报酬':>10}{'CAGR':>8}{'MDD':>9}{'R/MDD':>8}{'交易':>8}")
floor=None
for label,(c,tr) in variants.items():
    t,cg,m,r=stats(c)
    if 'V1' in label: floor=(t,cg,m,r)
    print(f"{label:<18}{t*100:>9.0f}%{cg*100:>7.1f}%{m*100:>8.1f}%{r:>8.2f}{tr:>8}")
zt,zcg,zm,zr=stats(z)
print(f"{'0050 B&H':<18}{zt*100:>9.0f}%{zcg*100:>7.1f}%{zm*100:>8.1f}%{zr:>8.2f}")

print(f"\n=== 裁决 (P7: 必须赢过 V1 纯动能地板) ===")
ft,fcg,fm,fr=floor
for label,(c,tr) in variants.items():
    if 'V1' in label: continue
    t,cg,m,r=stats(c)
    dmdd=m-fm      # 正=MDD改善(less negative)
    dret=(t-ft)*100
    dr=r-fr
    print(f"  {label}: ΔMDD {dmdd:+.1f}pp | Δ报酬 {dret:+.0f}pp | ΔR/MDD {dr:+.2f}")
    if dr>0.05: print(f"    → 🟢 风险调整后赢地板, 防御有效")
    elif dmdd>3 and dret>-20: print(f"    → 🟡 压低MDD但让利, 看取舍")
    else: print(f"    → 🔴 无改善或反伤 (R20预期): 减码/切换是负贡献, 维持纯动能")
