#!/usr/bin/env python3
"""闸门修正版: 只在极端偏多减码, 平时满仓照常。
测多种设计, 找风险调整后真正改善 B&H 的。
"""
import json, glob
import statistics as st, math
from collections import defaultdict
import backtest as B
days=B.days

inst=[];daily=[]
for f in sorted(glob.glob('data/finmind/inst_*.json')): inst+=json.load(open(f, encoding='utf-8'))
for f in sorted(glob.glob('data/finmind/daily_*.json')): daily+=json.load(open(f, encoding='utf-8'))
ib=defaultdict(lambda:[0,0])
for r in inst: ib[r['date']][0]+=r['long_open_interest_balance_volume']; ib[r['date']][1]+=r['short_open_interest_balance_volume']
ob=defaultdict(float)
for r in daily: ob[r['date']]+=r.get('open_interest',0)
retail={d:(ib[d][1]-ib[d][0])/ob[d] for d in ib if ob.get(d,0)>0}
d2i={f"{d[:4]}-{d[4:6]}-{d[6:]}":i for i,d in enumerate(days)}
ri={d2i[d]:v for d,v in retail.items() if d in d2i}
vals=sorted(retail.values())
def P(q): return vals[min(int(len(vals)*q),len(vals)-1)]
zret={i:B.adj_ret('0050',days[i-1],days[i]) for i in range(1,len(days))}
COST=0.0015

def run(rule):
    """rule(sig)->目标仓位; 平时1.0"""
    eq=1.0; pos_prev=1.0; rets=[]; curve=[]
    for i in range(1,len(days)):
        sig=ri.get(i-1)
        pos=rule(sig) if sig is not None else pos_prev
        r=zret.get(i,0)
        if pos!=pos_prev: eq*=(1-COST*abs(pos-pos_prev))
        step=pos*r; eq*=(1+step); rets.append(step); pos_prev=pos
        curve.append((days[i],eq,pos))
    return curve,rets

def metrics(curve,rets):
    v=[c[1] for c in curve]; tot=v[-1]-1; cagr=v[-1]**(252/len(v))-1
    pk=v[0];mdd=0
    for x in v: pk=max(pk,x);mdd=min(mdd,x/pk-1)
    sh=st.mean(rets)/st.pstdev(rets)*math.sqrt(252) if st.pstdev(rets)>0 else 0
    return tot,cagr,mdd,cagr/abs(mdd) if mdd else 0,sh,st.mean([c[2] for c in curve])

p90=P(.9);p80=P(.8);p95=P(.95)
designs={
  '纯B&H':                lambda s:1.0,
  'p90深红→空手':         lambda s:0.0 if s>=p90 else 1.0,
  'p90深红→半仓':         lambda s:0.5 if s>=p90 else 1.0,
  'p95极红→空手':         lambda s:0.0 if s>=p95 else 1.0,
  'p80红→减3成':          lambda s:0.7 if s>=p80 else 1.0,
  'p90空手+p80减3成':     lambda s:0.0 if s>=p90 else (0.7 if s>=p80 else 1.0),
}
print("=== 闸门修正版: 只在极端减码 (0050, 三年) ===\n")
print(f"{'设计':<20}{'总报酬':>9}{'CAGR':>8}{'MDD':>8}{'C/MDD':>8}{'Sharpe':>8}{'在场':>7}")
base=None
for name,rule in designs.items():
    c,r=run(rule); m=metrics(c,r)
    if name=='纯B&H': base=m
    flag=''
    if name!='纯B&H':
        if m[3]>base[3]*1.03: flag='🟢改善'
        elif m[3]>base[3]*0.98: flag='🟡持平'
        else: flag='🔴变差'
    print(f"{name:<20}{m[0]*100:>8.0f}%{m[1]*100:>7.1f}%{m[2]*100:>7.0f}%{m[3]:>8.2f}{m[4]:>8.2f}{m[5]*100:>6.0f}%  {flag}")

print(f"\n(p80={p80:+.1%} p90={p90:+.1%} p95={p95:+.1%})")
print("\n裁决: 找 C/MDD 或 Sharpe 明显 > 纯B&H 且在场比例高(少让利)的设计")
