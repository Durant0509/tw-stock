#!/usr/bin/env python3
"""分市況拆解 — 價值因子在哪個 regime 有價值?
regime = 0050 MA60 斜率 (分割調整序列, T6鐵則). bull/bear/range.
把各策略 & benchmark 的每日報酬按 regime 分桶, 桶內複利比較。
"""
import statistics as st
import backtest as B

days=B.days
MA=60; SLOPE=20

# 1) 分割調整的 0050 收盤序列 (用 adj_ret 累乘, 避開 2025-06 分割污染)
adj=[]; v=100.0
for i,d in enumerate(days):
    if i>0: v*=(1+B.adj_ret('0050',days[i-1],d))
    adj.append(v)

# 2) regime 分類: MA60 斜率 (t vs t-20)
def ma(i):
    seg=adj[max(0,i-MA+1):i+1]
    return sum(seg)/len(seg)
regime={}
for i in range(len(days)):
    if i<MA+SLOPE: regime[days[i]]='warmup'; continue
    slope=ma(i)/ma(i-SLOPE)-1
    regime[days[i]]= 'bull' if slope>0.02 else 'bear' if slope<-0.02 else 'range'

# 3) 取各曲線
curves={
  "價值×動能":B.run(0.5,0.5,"c")[0],
  "純估值":   B.run(1.0,0.0,"v")[0],
  "純動能":   B.run(0.0,1.0,"m")[0],
  "0050":     B.bench_0050(),
  "前150等權":B.bench_universe_ew(),
}
# 曲線 -> {date: daily_ret}
def to_ret(curve):
    out={}; prev=None
    for d,val in curve:
        if prev is not None and prev[1]>0: out[d]=val/prev[1]-1
        prev=(d,val)
    return out
rets={k:to_ret(c) for k,c in curves.items()}

# 4) 分桶複利
buckets=['bull','range','bear']
dates=[d for d,_ in curves["0050"]]
ndays={b:sum(1 for d in dates if regime.get(d)==b) for b in buckets}

print(f"=== 分市況拆解 {dates[0]}~{dates[-1]} ===")
print(f"regime 天數: bull {ndays['bull']} | range {ndays['range']} | bear {ndays['bear']}\n")
print(f"{'策略/benchmark':<12}{'bull':>12}{'range':>12}{'bear':>12}{'全期':>12}")
print("-"*60)
for k in curves:
    row=f"{k:<12}"
    for b in buckets+['ALL']:
        comp=1.0
        for d in dates:
            if b=='ALL' or regime.get(d)==b:
                comp*=(1+rets[k].get(d,0))
        row+=f"{(comp-1)*100:>11.1f}%"
    print(row)

print("\n【關鍵問題】價值因子(純估值)在哪個 regime 打贏 0050 或純動能?")
for b in buckets:
    def comp(k):
        c=1.0
        for d in dates:
            if regime.get(d)==b: c*=(1+rets[k].get(d,0))
        return (c-1)*100
    ve,mo,z=comp("純估值"),comp("純動能"),comp("0050")
    verdict=("✅ 純估值勝出" if ve>mo and ve>z else
             "⚠️ 純估值贏0050但輸動能" if ve>z else
             "🔴 純估值墊底")
    print(f"  {b:5s}: 純估值 {ve:+6.1f}% | 純動能 {mo:+6.1f}% | 0050 {z:+6.1f}%  → {verdict}")
