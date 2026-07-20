#!/usr/bin/env python3
"""散户反指当「进出场闸门」验证 + 当前状态判读。
不是策略, 是过滤器: 叠加在买进持有上, 看能否改善择时。
对照: 纯B&H vs B&H+散户闸门(红灯空手/黄灯半仓/绿灯满仓)。
关键指标: 风险调整后(CAGR/MDD, Sharpe) 是否改善。
"""
import json, glob
import statistics as st, math
from collections import defaultdict
import backtest as B
days=B.days

inst=[];daily=[]
for f in sorted(glob.glob('data/finmind/inst_*.json')): inst+=json.load(open(f))
for f in sorted(glob.glob('data/finmind/daily_*.json')): daily+=json.load(open(f))
ib=defaultdict(lambda:[0,0])
for r in inst: ib[r['date']][0]+=r['long_open_interest_balance_volume']; ib[r['date']][1]+=r['short_open_interest_balance_volume']
ob=defaultdict(float)
for r in daily: ob[r['date']]+=r.get('open_interest',0)
retail={d:(ib[d][1]-ib[d][0])/ob[d] for d in ib if ob.get(d,0)>0}
d2i={f"{d[:4]}-{d[4:6]}-{d[6:]}":i for i,d in enumerate(days)}
ri={d2i[d]:v for d,v in retail.items() if d in d2i}

vals=sorted(retail.values())
p80=vals[int(len(vals)*.8)]; p20=vals[int(len(vals)*.2)]
p90=vals[int(len(vals)*.9)]; p10=vals[int(len(vals)*.1)]
zret={i:B.adj_ret('0050',days[i-1],days[i]) for i in range(1,len(days))}
COST=0.0015

def run(gated):
    """gated=False: 纯B&H; True: 散户闸门调仓"""
    eq=1.0; curve=[]; pos_prev=1.0; rets=[]
    for i in range(1,len(days)):
        if not gated: pos=1.0
        else:
            sig=ri.get(i-1)
            if sig is None: pos=pos_prev
            elif sig>=p80: pos=0.0    # 红灯: 极端偏多 空手
            elif sig<=p20: pos=1.0    # 绿灯: 极端偏空 满仓
            else: pos=0.5             # 黄灯: 半仓
        r=zret.get(i,0)
        if gated and pos!=pos_prev: eq*=(1-COST*abs(pos-pos_prev))
        step=pos*r; eq*=(1+step); rets.append(step); pos_prev=pos
        curve.append((days[i],eq,pos))
    return curve,rets

def metrics(curve,rets):
    v=[c[1] for c in curve]
    tot=v[-1]-1; cagr=v[-1]**(252/len(v))-1
    pk=v[0];mdd=0
    for x in v: pk=max(pk,x);mdd=min(mdd,x/pk-1)
    sh=(st.mean(rets)/st.pstdev(rets)*math.sqrt(252)) if st.pstdev(rets)>0 else 0
    # 在场比例
    inpos=st.mean([c[2] for c in curve])
    return tot,cagr,mdd,cagr/abs(mdd) if mdd else 0,sh,inpos

bh,bhr=run(False)
gt,gtr=run(True)
mb=metrics(bh,bhr); mg=metrics(gt,gtr)
print("=== 散户闸门 vs 纯买进持有 (0050, 三年) ===\n")
print(f"{'指标':<16}{'纯B&H':>12}{'B&H+散户闸门':>16}")
print(f"{'总报酬':<16}{mb[0]*100:>11.0f}%{mg[0]*100:>15.0f}%")
print(f"{'CAGR':<16}{mb[1]*100:>11.1f}%{mg[1]*100:>15.1f}%")
print(f"{'MDD':<16}{mb[2]*100:>11.0f}%{mg[2]*100:>15.0f}%")
print(f"{'CAGR/MDD':<16}{mb[3]:>12.2f}{mg[3]:>16.2f}")
print(f"{'Sharpe':<16}{mb[4]:>12.2f}{mg[4]:>16.2f}")
print(f"{'平均在场比例':<16}{mb[5]*100:>11.0f}%{mg[5]*100:>15.0f}%")

print(f"\n=== 闸门有效性裁决 ===")
if mg[3]>mb[3]*1.05: print(f"  🟢 闸门改善风险调整报酬 (CAGR/MDD {mg[3]:.2f} vs {mb[3]:.2f})")
elif mg[2]>mb[2]+0.05: print(f"  🟡 闸门降低回撤但让利报酬 (MDD {mg[2]*100:.0f}% vs {mb[2]*100:.0f}%)")
else: print(f"  🔴 闸门无改善")

# === 当前状态判读 ===
cur_i=len(days)-1
cur_sig=ri.get(cur_i)
print(f"\n=== 当前进出场判读 ({days[-1][:4]}-{days[-1][4:6]}-{days[-1][6:]}) ===")
if cur_sig is not None:
    pctl=100*sum(1 for v in vals if v<cur_sig)/len(vals)
    if cur_sig>=p90: light="🔴🔴 深红灯 (极端偏多前10%)"; act="强烈建议减码/禁新仓"
    elif cur_sig>=p80: light="🔴 红灯 (偏多前20%)"; act="谨慎, 不宜新仓"
    elif cur_sig<=p10: light="🟢🟢 深绿灯 (极端偏空前10%)"; act="可积极加码"
    elif cur_sig<=p20: light="🟢 绿灯 (偏空后20%)"; act="进场时机佳"
    else: light="🟡 黄灯 (中间)"; act="正常仓位"
    print(f"  散户多空比: {cur_sig:+.1%} (历史第 {pctl:.0f} 百分位)")
    print(f"  闸门: {light}")
    print(f"  建议: {act}")

# 输出网页用 (近一年闸门轨迹)
out={'metrics':{'bh':mb,'gate':mg},'current':{
  'date':f"{days[-1][:4]}-{days[-1][4:6]}-{days[-1][6:]}",
  'ratio':cur_sig,'pctl':100*sum(1 for v in vals if v<cur_sig)/len(vals) if cur_sig else None}}
# 闸门信号历史
gate_hist=[]
for i in range(1,len(days),3):
    sig=ri.get(i)
    if sig is None: continue
    lv='red' if sig>=p80 else 'green' if sig<=p20 else 'yellow'
    gate_hist.append([days[i],round(sig,3),lv])
out['hist']=gate_hist
out['bands']={'p80':round(p80,3),'p20':round(p20,3),'p90':round(p90,3),'p10':round(p10,3)}
out['curves']={'bh':[[c[0],round(c[1],3)] for c in bh[::5]],'gate':[[c[0],round(c[1],3)] for c in gt[::5]]}
json.dump(out,open('gate_data.json','w'),ensure_ascii=False)
print("\ngate_data.json 输出完成")
