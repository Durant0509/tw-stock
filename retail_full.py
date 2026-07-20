#!/usr/bin/env python3
"""台指期散户多空比 完整三年详细分析 (正版算法)。
散户多空比 = (散户多单 - 散户空单) / 全市场未平仓
         = ((全市场-法人多) - (全市场-法人空)) / 全市场
         = (法人空 - 法人多) / 全市场   [散户是法人对手方]
资料: FinMind inst(三法人未平仓) + daily(全市场OI). 2022-07~2026-07.

详细验证:
  1. 完整三年 极端偏多/偏空 → fwd报酬 (反转强度)
  2. 跨 regime (含2022熊)
  3. 百分位细分 (越极端越准?)
  4. 子期间稳定性 (前后半)
  5. 持有期敏感度
"""
import json, glob
import statistics as st
from collections import defaultdict
import backtest as B

# --- 载入 FinMind ---
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

# 散户多空比 (日期用 YYYY-MM-DD)
retail={}
for d in inst_by:
    il,ish=inst_by[d]; tot=oi_by.get(d,0)
    if tot>0: retail[d]=(ish-il)/tot   # 散户多空净/全市场
rdates=sorted(retail)
print(f"散户多空比: {len(rdates)}天 {rdates[0]}~{rdates[-1]}")

# --- 大盘报酬 (0050 分割调整, 转 YYYY-MM-DD 对齐) ---
days=B.days  # YYYYMMDD
adj=[100.0]
for i in range(1,len(days)): adj.append(adj[-1]*(1+B.adj_ret('0050',days[i-1],days[i])))
d2i={f"{d[:4]}-{d[4:6]}-{d[6:]}":i for i,d in enumerate(days)}
def fwd(dstr,f):
    i=d2i.get(dstr)
    if i is None or i+f>=len(adj): return None
    return adj[i+f]/adj[i]-1

# regime
def ma(i): seg=adj[max(0,i-60+1):i+1]; return sum(seg)/len(seg)
def regime(dstr):
    i=d2i.get(dstr)
    if i is None or i<80: return 'warmup'
    s=ma(i)/ma(i-20)-1
    return 'bull' if s>0.02 else 'bear' if s<-0.02 else 'range'

vals=sorted(retail.values())
p80=vals[int(len(vals)*.8)]; p20=vals[int(len(vals)*.2)]
p90=vals[int(len(vals)*.9)]; p10=vals[int(len(vals)*.1)]
print(f"分布: p10={p10:+.3f} p20={p20:+.3f} 中位={vals[len(vals)//2]:+.3f} p80={p80:+.3f} p90={p90:+.3f}\n")

def m(x): return st.mean(x)*100 if x else 0
def wr(x): return 100*sum(1 for v in x if v>0)/len(x) if x else 0

# === 1. 完整三年 极端 → fwd ===
print("=== 1. 完整三年: 散户极端偏多/偏空 → 未来报酬 ===")
print(f"{'持有期':<8}{'极端偏多(p80+)':>16}{'极端偏空(p20-)':>16}{'偏多-偏空':>12}")
for f in [5,10,20,40]:
    hi=[fwd(d,f) for d in retail if retail[d]>=p80]; hi=[x for x in hi if x is not None]
    lo=[fwd(d,f) for d in retail if retail[d]<=p20]; lo=[x for x in lo if x is not None]
    print(f"fwd{f:<5}{m(hi):>14.2f}%{m(lo):>15.2f}%{m(hi)-m(lo):>10.2f}pp")

# === 2. 跨 regime (fwd20) ===
print("\n=== 2. 跨 regime (fwd20, 含2022熊) ===")
print(f"{'regime':<8}{'极端偏多后':>14}{'极端偏空后':>14}{'样本':>10}")
for reg in ['bull','range','bear']:
    hi=[fwd(d,20) for d in retail if retail[d]>=p80 and regime(d)==reg]; hi=[x for x in hi if x is not None]
    lo=[fwd(d,20) for d in retail if retail[d]<=p20 and regime(d)==reg]; lo=[x for x in lo if x is not None]
    print(f"{reg:<8}{m(hi):>13.2f}%{m(lo):>13.2f}%{f'{len(hi)}/{len(lo)}':>10}")

# === 3. 百分位细分 (越极端越准?) fwd20 ===
print("\n=== 3. 百分位细分 (fwd20, 看单调性) ===")
buckets=[(0,10,'最偏空p0-10'),(10,30,'p10-30'),(30,70,'中间p30-70'),(70,90,'p70-90'),(90,100,'最偏多p90-100')]
for lo_p,hi_p,name in buckets:
    lv=vals[int(len(vals)*lo_p/100)]; hv=vals[min(int(len(vals)*hi_p/100),len(vals)-1)]
    rs=[fwd(d,20) for d in retail if lv<=retail[d]<hv]; rs=[x for x in rs if x is not None]
    print(f"  {name:<16} avg {m(rs):+6.2f}% 胜率{wr(rs):.0f}% (n={len(rs)})")

# === 4. 子期间稳定性 ===
print("\n=== 4. 子期间稳定性 (前半 vs 后半, 极端偏多 fwd20) ===")
mid=rdates[len(rdates)//2]
for label,sub in [('前半',[d for d in rdates if d<mid]),('后半',[d for d in rdates if d>=mid])]:
    hi=[fwd(d,20) for d in sub if retail[d]>=p80]; hi=[x for x in hi if x is not None]
    lo=[fwd(d,20) for d in sub if retail[d]<=p20]; lo=[x for x in lo if x is not None]
    print(f"  {label}({sub[0]}~{sub[-1]}): 偏多后{m(hi):+.2f}% 偏空后{m(lo):+.2f}% 差{m(hi)-m(lo):+.2f}pp")

print("\n=== 裁决 ===")
print("反向指标稳健 <=> ①偏多-偏空为负且明显 ②跨regime一致 ③百分位单调 ④前后半都成立")
