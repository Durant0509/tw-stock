#!/usr/bin/env python3
"""散户多空比 真回测 (按信号进出场, 画权益曲线 vs benchmark)。
台指散户反指 + 前150个股融资融券, 三年, 输出 JSON 供网页。

台指策略逻辑 (反向指标):
  散户极端偏空(p20-) → 做多 (满仓0050)
  散户极端偏多(p80+) → 空手 (避开下跌)
  中间 → 半仓
个股策略: 每周选「券资比最高/最低」组, 看反指/顺势
"""
import json, glob
import statistics as st
from collections import defaultdict
import backtest as B
import ls_loader as LS
days=B.days

# --- 台指散户多空比 ---
inst=[];daily=[]
for f in sorted(glob.glob('data/finmind/inst_*.json')): inst+=json.load(open(f))
for f in sorted(glob.glob('data/finmind/daily_*.json')): daily+=json.load(open(f))
ib=defaultdict(lambda:[0,0])
for r in inst: ib[r['date']][0]+=r['long_open_interest_balance_volume']; ib[r['date']][1]+=r['short_open_interest_balance_volume']
ob=defaultdict(float)
for r in daily: ob[r['date']]+=r.get('open_interest',0)
retail={d:(ib[d][1]-ib[d][0])/ob[d] for d in ib if ob.get(d,0)>0}

# 0050 报酬 (分割调整), 日期 YYYYMMDD
zret={i:B.adj_ret('0050',days[i-1],days[i]) for i in range(1,len(days))}
d2i={f"{d[:4]}-{d[4:6]}-{d[6:]}":i for i,d in enumerate(days)}

vals=sorted(retail.values()); p80=vals[int(len(vals)*.8)]; p20=vals[int(len(vals)*.2)]
COST=0.0015  # 单边成本(期货较低, 保守)

def bt_taifutures():
    """台指散户反指: 依前一日信号决定今日仓位"""
    eq=1.0; ez=1.0; curve=[]; pos_prev=0.5
    # 建 index->retail 值 (用当日已知的前一交易日信号)
    ri={}
    for d,v in retail.items():
        if d in d2i: ri[d2i[d]]=v
    for i in range(1,len(days)):
        # 用 i-1 的信号 (避免look-ahead)
        sig=ri.get(i-1)
        if sig is None: pos=pos_prev
        elif sig<=p20: pos=1.0    # 散户极空→做多
        elif sig>=p80: pos=0.0    # 散户极多→空手
        else: pos=0.5
        r=zret.get(i,0)
        if pos!=pos_prev: eq*=(1-COST*abs(pos-pos_prev))  # 换仓成本
        eq*=(1+pos*r); ez*=(1+r); pos_prev=pos
        curve.append((days[i],eq,ez,pos))
    return curve

print("跑 台指散户反指回测...")
tf=bt_taifutures()

def stats(curve,eqi=1,bmi=2):
    ev=[c[eqi] for c in curve]; bv=[c[bmi] for c in curve]
    def mdd(v):
        pk=v[0];m=0
        for x in v: pk=max(pk,x);m=min(m,x/pk-1)
        return m
    def cagr(v): return v[-1]**(252/len(v))-1
    return (ev[-1]-1,cagr(ev),mdd(ev)),(bv[-1]-1,cagr(bv),mdd(bv))

s,b=stats(tf)
print(f"  策略: 报酬{s[0]*100:+.0f}% CAGR{s[1]*100:+.1f}% MDD{s[2]*100:.0f}%")
print(f"  0050: 报酬{b[0]*100:+.0f}% CAGR{b[1]*100:+.1f}% MDD{b[2]*100:.0f}%")

# --- 个股融资融券反指 (long-short: 券资比低组做多, 高组做空 or 只做多低组) ---
print("跑 前150个股融资融券回测...")
mdays=LS.margin_days()
mcache={}
for ds in mdays:
    m,_=LS.margin_day(ds);
    if m: mcache[ds]=m
uni_at={}
for ti in range(0,len(days),20):
    t=days[ti]; mc=[]
    for code,s2 in B.DD[t]["stocks"].items():
        c=s2["close"]; sh=B.co.get(code,{}).get("shares")
        if c and sh and code.isdigit() and len(code)==4: mc.append((c*sh,code))
    mc.sort(reverse=True); uni_at[ti]={c for _,c in mc[:150]}
def uni_for(i): return uni_at[(i//20)*20]

def bt_stock(mode='low_short'):
    """每周rebalance, 选券资比某组等权持有。
    mode: 'low_short'=券资比低(空方少)组; 'high_short'=券资比高(轧空)组"""
    eq=1.0; curve=[]; hold=[]; STEP=5
    rebal=set(range(80,len(days),STEP))
    STOCK_COST=0.003
    for i in range(80,len(days)):
        d=days[i]; dp=days[i-1]
        if hold:
            r=st.mean([B.adj_ret(c,dp,d) for c in hold])
            eq*=(1+r)
        if i in rebal and d in mcache:
            uni=uni_for(i); rows=[]
            for code in uni:
                if code in mcache[d]:
                    fin,short=mcache[d][code]
                    if fin>0: rows.append((code,short/fin))
            if len(rows)>=20:
                rows.sort(key=lambda x:x[1])
                q=max(3,len(rows)//5)
                new=[c for c,_ in (rows[-q:] if mode=='high_short' else rows[:q])]
                if set(new)!=set(hold): eq*=(1-STOCK_COST)
                hold=new
        curve.append((days[i],eq))
    return curve

sk_low=bt_stock('low_short')
sk_high=bt_stock('high_short')
# benchmark: 前150等权
def bt_ew():
    eq=1.0;curve=[];hold=[];STEP=5
    rebal=set(range(80,len(days),STEP))
    for i in range(80,len(days)):
        d=days[i];dp=days[i-1]
        if hold: eq*=(1+st.mean([B.adj_ret(c,dp,d) for c in hold]))
        if i in rebal: hold=list(uni_for(i))
        curve.append((days[i],eq))
    return curve
ew=bt_ew()

def sfin(curve,i=1):
    v=[c[i] for c in curve];pk=v[0];m=0
    for x in v:pk=max(pk,x);m=min(m,x/pk-1)
    return v[-1]-1,v[-1]**(252/len(v))-1,m
for nm,cv in [('券资比低组(空方少)',sk_low),('券资比高组(轧空)',sk_high),('前150等权',ew)]:
    r=sfin(cv); print(f"  {nm}: 报酬{r[0]*100:+.0f}% CAGR{r[1]*100:+.1f}% MDD{r[2]*100:.0f}%")

# --- 输出网页 JSON (降采样) ---
def ds_curve(curve,cols):
    return [[c[0]]+[round(c[k],4) for k in cols] for c in curve[::5]]
out={
  'taifutures':{'curve':ds_curve(tf,[1,2]),'stats':{'strat':s,'bench':b}},
  'stock':{
    'low':ds_curve([(c[0],c[1]) for c in sk_low],[1]),
    'high':ds_curve([(c[0],c[1]) for c in sk_high],[1]),
    'ew':ds_curve([(c[0],c[1]) for c in ew],[1]),
    'stats':{'low':sfin(sk_low),'high':sfin(sk_high),'ew':sfin(ew)}
  }
}
json.dump(out,open('ls_backtest_data.json','w'),ensure_ascii=False)
print("\nls_backtest_data.json 输出完成")
