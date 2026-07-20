#!/usr/bin/env python3
"""路B: 单独审判「族群动能+MA60」报酬引擎。
同一套严格标准: vs 0050 / DSR / MC 打乱顺序。不因报酬高放水。
"""
import math, random
import statistics as st
import backtest as B
from validation import daily_returns, mdd_from_rets, sharpe, skew_kurt, norm_cdf, norm_ppf

random.seed(42)

def full_stats(curve):
    vals=[v for _,v in curve]
    tot=vals[-1]/vals[0]-1; yrs=len(vals)/252; cagr=vals[-1]**(1/yrs)-1
    peak=vals[0]; mdd=0
    for v in vals: peak=max(peak,v); mdd=min(mdd,v/peak-1)
    return tot,cagr,mdd,cagr/abs(mdd) if mdd else 0

def dsr(rets, n_trials):
    T=len(rets); sr=sharpe(rets); srd=sr/math.sqrt(252)
    sk,ku=skew_kurt(rets); emc=0.5772156649
    sd=math.sqrt(abs((1/T)*(1-sk*srd+(ku-1)/4*srd**2)))
    sr0=sd*((1-emc)*norm_ppf(1-1/n_trials)+emc*norm_ppf(1-1/(n_trials*math.e)))
    denom=math.sqrt(1-sk*srd+(ku-1)/4*srd**2)
    return norm_cdf(((srd-sr0)*math.sqrt(T-1))/denom), sr, sr0*math.sqrt(252), sk, ku

print("跑 族群动能+MA60 引擎...")
eng,te=B.run(0.0,1.0,"engine",B.candidates_ma60only)
print("跑 撿便宜 5:5 (对照)...")
chp,tc=B.run(0.5,0.5,"cheap")
z=B.bench_0050()

print(f"\n=== 报酬引擎 vs 撿便宜 vs 0050 (干净 {B.days[80]}~{B.days[-1]}) ===")
print(f"{'':16}{'总报酬':>10}{'CAGR':>8}{'MDD':>9}{'R/MDD':>8}")
for name,c in [("族群动能+MA60",eng),("撿便宜5:5",chp),("0050 B&H",z)]:
    t,cg,m,r=full_stats(c)
    print(f"{name:<16}{t*100:>9.0f}%{cg*100:>7.1f}%{m*100:>8.1f}%{r:>8.2f}")

# 引擎 vs 0050 是关键问题
te_t,te_cg,te_m,te_r=full_stats(eng)
z_t,z_cg,z_m,z_r=full_stats(z)
print(f"\n引擎 vs 0050: 报酬 {(te_t-z_t)*100:+.0f}pp | R/MDD {te_r:.2f} vs {z_r:.2f}")

rets=daily_returns(eng)
print(f"\n=== DSR (校正多重检验, N=8 变体) ===")
d,sr,sr0,sk,ku=dsr(rets,8)
print(f"  年化 Sharpe {sr:.3f} | 门槛 SR0 {sr0:.3f} | skew {sk:.2f} kurt {ku:.2f}")
print(f"  DSR = {d:.3f}  {'✅ 显著' if d>0.95 else '🟡 边际' if d>0.9 else '🔴 不显著'}")

print(f"\n=== MC 打乱顺序 (1000次) ===")
hist=mdd_from_rets(rets); mdds=[]
for _ in range(1000):
    sh=rets[:]; random.shuffle(sh); mdds.append(mdd_from_rets(sh))
mdds.sort()
print(f"  历史 MDD {hist*100:.1f}% | p50 {mdds[500]*100:.1f}% | p95 {mdds[50]*100:.1f}% | p99 {mdds[10]*100:.1f}% | 最坏 {mdds[0]*100:.1f}%")

print(f"\n=== 裁决 ===")
beats=te_t>z_t; rmdd_better=te_r>z_r
print(f"  报酬赢0050: {'✅' if beats else '🔴'} | 风险调整赢0050: {'✅' if rmdd_better else '🔴'} | DSR: {d:.2f}")
if beats and d>0.9: print("  → 🟢 真报酬引擎, 值得当策略核心")
elif rmdd_better and d>0.9: print("  → 🟡 风险调整后有edge, 但raw报酬输0050")
elif d<=0.9: print("  → 🔴 DSR不显著: 高报酬可能是选择偏差矇到的, 不是真edge")
else: print("  → 🔴 报酬和风险调整都输0050, 无独立价值")
