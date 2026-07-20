#!/usr/bin/env python3
"""策略健康度仪表板: 把验证过的因子上滚动体温计, 自动亮灯启用/暂停。
实现「辨别市场→切对应策略→失效暂停」构想。反应式(看策略近期体温)非预测式。

四个策略 + 各自 benchmark:
  1. 动能引擎(族群动能+MA60)  vs 0050  — 牛市报酬
  2. 撿便宜(低PE)             vs 0050  — 熊市防御
  3. 回撤均值回归             vs 随机   — 熊市反弹
  4. 散户多空反指             vs 0    — 反向情绪
体温 = 滚动窗超额报酬; 输出 当前灯号 + 历史轨迹 JSON 供网页。
"""
import json, glob
import statistics as st
from collections import defaultdict
import backtest as B
days=B.days

# --- 共用: 0050 报酬/regime ---
adj=[100.0]
for i in range(1,len(days)): adj.append(adj[-1]*(1+B.adj_ret('0050',days[i-1],days[i])))
def ma(i): seg=adj[max(0,i-60+1):i+1]; return sum(seg)/len(seg)
def regime_i(i):
    if i<80: return 'warmup'
    s=ma(i)/ma(i-20)-1
    return 'bull' if s>0.02 else 'bear' if s<-0.02 else 'range'

ROLL=63   # 滚动窗 ~一季

# --- 策略1: 动能引擎 (用现成 run) ---
print("跑 动能引擎...")
eng,_=B.run(0.0,1.0,"eng",B.candidates_ma60only)
print("跑 撿便宜...")
chp,_=B.run(0.5,0.5,"chp")

def curve_daily_ret(curve):
    """curve=[(date,val)] -> {i: ret}"""
    out={}; prev=None
    for d,v in curve:
        i=days.index(d)
        if prev is not None and prev[1]>0: out[i]=v/prev[1]-1
        prev=(i,v)
    return out
eng_r=curve_daily_ret(eng); chp_r=curve_daily_ret(chp)
z_r={i:adj[i]/adj[i-1]-1 for i in range(1,len(adj))}

def rolling_excess(strat_r, bench_r, label):
    """每日算过去ROLL天 策略超额(累积) → 体温 + 灯号轨迹"""
    idxs=sorted(strat_r)
    traj=[]  # (date, excess%, light)
    for k in range(ROLL,len(idxs)):
        window=idxs[k-ROLL:k]
        s=1.0; b=1.0
        for i in window:
            s*=(1+strat_r.get(i,0)); b*=(1+bench_r.get(i,0))
        exc=(s-b)*100
        light='green' if exc>1 else 'red' if exc<-1 else 'gray'
        traj.append((days[idxs[k]], round(exc,2), light))
    return traj

# --- 散户反指: 体温=滚动"偏多后报酬"(负=有效) ---
inst=[]; daily=[]
for f in sorted(glob.glob('data/finmind/inst_*.json')): inst+=json.load(open(f))
for f in sorted(glob.glob('data/finmind/daily_*.json')): daily+=json.load(open(f))
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
d2i={f"{d[:4]}-{d[4:6]}-{d[6:]}":i for i,d in enumerate(days)}
vals=sorted(retail.values()); p80=vals[int(len(vals)*.8)]

def retail_traj():
    """滚动: 过去~2季偏多信号后20日报酬均值, 负=反指有效"""
    rd=sorted(retail); traj=[]
    for k in range(120,len(rd)):
        window=rd[k-120:k]
        rets=[]
        for d in window:
            if retail[d]>=p80:
                i=d2i.get(d)
                if i and i+20<len(adj): rets.append(adj[i+20]/adj[i]-1)
        if len(rets)>=3:
            avg=st.mean(rets)*100
            light='green' if avg<-1 else 'red' if avg>1 else 'gray'
            traj.append((rd[k].replace('-',''),round(avg,2),light))
    return traj

dash={
  'engine': rolling_excess(eng_r,z_r,'动能引擎'),
  'cheap':  rolling_excess(chp_r,z_r,'撿便宜'),
  'retail': retail_traj(),
}
# 当前灯号 + regime
cur_i=len(days)-1
dash['current']={
  'date':f"{days[-1][:4]}-{days[-1][4:6]}-{days[-1][6:]}",
  'regime':regime_i(cur_i),
  'engine':dash['engine'][-1] if dash['engine'] else None,
  'cheap':dash['cheap'][-1] if dash['cheap'] else None,
  'retail':dash['retail'][-1] if dash['retail'] else None,
}
json.dump(dash,open('dashboard_data.json','w'),ensure_ascii=False)

# 文字摘要
print(f"\n=== 策略健康度仪表板 (截至 {dash['current']['date']}) ===")
print(f"当前大盘 regime: {dash['current']['regime']}\n")
names={'engine':'动能引擎(族群动能+MA60)','cheap':'撿便宜(低PE防御)','retail':'散户多空反指'}
for k in ['engine','cheap','retail']:
    c=dash['current'][k]
    if c:
        light={'green':'🟢启用','red':'🔴暂停','gray':'⚪中性'}[c[2]]
        print(f"  {names[k]:<24} 体温 {c[1]:+.1f} → {light}")
# 近一年灯号变化次数(稳定性)
print(f"\n=== 各策略近期灯号轨迹 (最后8个采样) ===")
for k in ['engine','cheap','retail']:
    tail=dash[k][-8:]
    seq=' '.join({'green':'🟢','red':'🔴','gray':'⚪'}[t[2]] for t in tail)
    print(f"  {names[k]:<24} {seq}")
print("\ndashboard_data.json 已输出 (供网页)")
