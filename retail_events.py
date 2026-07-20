#!/usr/bin/env python3
"""A: 查后半段 -10.97pp 是少数事件灌的还是稳定? + 策略健康度滚动监控。
列出每次「极端偏多」信号 + 之后报酬, 看分布 (少数大赢 vs 普遍有效)。
滚动监控: 每季度算反指近期效力, 侦测失效/恢复。
"""
import json, glob
import statistics as st
from collections import defaultdict
import backtest as B

inst=[]
for f in sorted(glob.glob('data/finmind/inst_*.json')): inst+=json.load(open(f, encoding='utf-8'))
daily=[]
for f in sorted(glob.glob('data/finmind/daily_*.json')): daily+=json.load(open(f, encoding='utf-8'))
inst_by=defaultdict(lambda:[0,0])
for r in inst:
    inst_by[r['date']][0]+=r['long_open_interest_balance_volume']
    inst_by[r['date']][1]+=r['short_open_interest_balance_volume']
oi_by=defaultdict(float)
for r in daily: oi_by[r['date']]+=r.get('open_interest',0)
retail={}
for d in inst_by:
    il,ish=inst_by[d]; tot=oi_by.get(d,0)
    if tot>0: retail[d]=(ish-il)/tot
rdates=sorted(retail)

days=B.days
adj=[100.0]
for i in range(1,len(days)): adj.append(adj[-1]*(1+B.adj_ret('0050',days[i-1],days[i])))
d2i={f"{d[:4]}-{d[4:6]}-{d[6:]}":i for i,d in enumerate(days)}
def fwd(dstr,f):
    i=d2i.get(dstr)
    if i is None or i+f>=len(adj): return None
    return adj[i+f]/adj[i]-1

vals=sorted(retail.values()); p80=vals[int(len(vals)*.8)]

# === A1: 后半段每次极端偏多信号 (去重: 连续偏多算一次事件) ===
mid=rdates[len(rdates)//2]
print(f"=== A: 后半段({mid}起) 极端偏多信号明细 (fwd20报酬) ===")
sig_days=[d for d in rdates if d>=mid and retail[d]>=p80]
# 聚合连续信号成"事件"(间隔>10交易日算新事件)
events=[]; cur=[]
for d in sig_days:
    if cur and d2i.get(d,0)-d2i.get(cur[-1],0)>10: events.append(cur); cur=[]
    cur.append(d)
if cur: events.append(cur)
print(f"后半段 {len(sig_days)} 个偏多日, 聚合成 {len(events)} 个独立事件:\n")
ev_rets=[]
for ev in events:
    d0=ev[0]; r=fwd(d0,20)
    if r is not None:
        ev_rets.append(r)
        print(f"  {d0} (持续{len(ev)}日, 散户多空比{retail[d0]:+.1%}) → fwd20 {r*100:+.1f}%")
print(f"\n独立事件 fwd20: n={len(ev_rets)}, avg {st.mean(ev_rets)*100:+.2f}%, "
      f"中位 {st.median(ev_rets)*100:+.2f}%, 负报酬 {sum(1 for r in ev_rets if r<0)}/{len(ev_rets)}")
print("→ 若 avg 靠1-2次大跌灌 → 中位会接近0; 若普遍有效 → 中位也明显负")

# === A2: 策略健康度滚动监控 (每季反指效力) ===
print(f"\n=== 策略健康度: 滚动季度反指效力 (偏多后-偏空后, 负=反指有效) ===")
p20=vals[int(len(vals)*.2)]
quarters=defaultdict(lambda:{'hi':[],'lo':[]})
for d in rdates:
    q=f"{d[:4]}Q{(int(d[5:7])-1)//3+1}"
    r=fwd(d,20)
    if r is None: continue
    if retail[d]>=p80: quarters[q]['hi'].append(r)
    elif retail[d]<=p20: quarters[q]['lo'].append(r)
print(f"{'季度':<8}{'偏多后':>10}{'偏空后':>10}{'效力(多-空)':>14}{'状态':>8}")
for q in sorted(quarters):
    hi=quarters[q]['hi']; lo=quarters[q]['lo']
    if hi and lo:
        eff=st.mean(hi)*100-st.mean(lo)*100
        status='🟢有效' if eff<-2 else '🔴失效' if eff>2 else '⚪中性'
        print(f"{q:<8}{st.mean(hi)*100:>9.1f}%{st.mean(lo)*100:>9.1f}%{eff:>13.1f}pp{status:>9}")
