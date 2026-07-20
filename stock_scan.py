#!/usr/bin/env python3
"""个股诊断: 输入代号 → 个股状况(动能/估值/趋势/筹码) + 大盘背景(regime/散户闸门)。
个股专属因子会随股票变; 大盘背景所有股共用。
"""
import sys, json, glob
import statistics as st
from collections import defaultdict
import backtest as B
import ls_loader as LS
days=B.days

# === 大盘背景 (共用) ===
adj=[100.0]
for i in range(1,len(days)): adj.append(adj[-1]*(1+B.adj_ret('0050',days[i-1],days[i])))
def ma_i(i): seg=adj[max(0,i-60+1):i+1]; return sum(seg)/len(seg)
cur=len(days)-1
slope=ma_i(cur)/ma_i(cur-20)-1
regime='bull' if slope>0.02 else 'bear' if slope<-0.02 else 'range'
# 散户多空比闸门
inst=[];daily=[]
for f in sorted(glob.glob('data/finmind/inst_*.json')): inst+=json.load(open(f, encoding='utf-8'))
for f in sorted(glob.glob('data/finmind/daily_*.json')): daily+=json.load(open(f, encoding='utf-8'))
ib=defaultdict(lambda:[0,0])
for r in inst: ib[r['date']][0]+=r['long_open_interest_balance_volume']; ib[r['date']][1]+=r['short_open_interest_balance_volume']
ob=defaultdict(float)
for r in daily: ob[r['date']]+=r.get('open_interest',0)
retail={d:(ib[d][1]-ib[d][0])/ob[d] for d in ib if ob.get(d,0)>0}
rvals=sorted(retail.values()); rcur=retail[max(retail)]
rpctl=100*sum(1 for v in rvals if v<rcur)/len(rvals)
p95=rvals[int(len(rvals)*.95)]; p90=rvals[int(len(rvals)*.9)]; p20=rvals[int(len(rvals)*.2)]
gate='🔴減碼' if rcur>=p95 else '🟠謹慎' if rcur>=p90 else '🟢進場佳' if rcur<=p20 else '⚪正常'

# 券资比(大盘)
_,mkt_short=LS.margin_day(days[-1]) if days[-1] in [d[:8] for d in []] else (None,None)

def adj_px(code):
    px=[100.0]
    for i in range(1,len(days)): px.append(px[-1]*(1+B.adj_ret(code,days[i-1],days[i])))
    return px

# 族群指数动能 (个股所属产业)
def sector_mom(code):
    ind=B.co.get(code,{}).get('industry')
    if not ind: return None,None
    nm=B.guess(ind)
    if not nm: return ind,None
    c1=B.DD[days[-1]]['indices'].get(nm); c0=B.DD[days[-21]]['indices'].get(nm)
    if c1 and c0: return ind,(c1/c0-1)
    return ind,None

def diagnose(code):
    s=B.DD[days[-1]]['stocks'].get(code)
    if not s or not s['close']: return None
    px=adj_px(code)
    close=s['close']; pe=s['pe']
    # 趋势: 距52週高、MA60
    look=min(252,len(px)); hi52=max(px[-look:]); from_high=px[-1]/hi52-1
    ma60=sum(px[-60:])/60; above_ma60=px[-1]/ma60-1
    ma20=sum(px[-20:])/20
    # 动能: 60日报酬
    ret60=px[-1]/px[-61]-1 if len(px)>61 else None
    # 估值: PE 在自己3年区间位阶
    pe_hist=[]
    for d in days[-750:]:
        st2=B.DD[d]['stocks'].get(code)
        if st2 and st2['pe'] and st2['pe']>0: pe_hist.append(st2['pe'])
    pe_pctl=None
    if pe and pe>0 and len(pe_hist)>50:
        pe_pctl=100*sum(1 for x in pe_hist if x<pe)/len(pe_hist)
    # 族群动能
    ind,smom=sector_mom(code)
    # 券资比
    m,_=LS.margin_day(days[-1])
    ratio=None
    if m and code in m:
        fin,short=m[code]
        if fin>0: ratio=short/fin
    return {'code':code,'name':s['name'],'close':close,'pe':pe,'pe_pctl':pe_pctl,
            'from_high':from_high*100,'above_ma60':above_ma60*100,'ret60':ret60*100 if ret60 else None,
            'above_ma20':(px[-1]/ma20-1)*100,'industry':ind,'sector_mom':smom*100 if smom is not None else None,
            'short_ratio':ratio}

def verdict(d):
    """综合判读"""
    pts=[]; score=0
    # 趋势
    if d['above_ma60']>0: pts.append('✅ 站上MA60(多头)'); score+=1
    else: pts.append('❌ 跌破MA60(空头)'); score-=1
    # 动能
    if d['ret60'] and d['ret60']>20: pts.append(f"✅ 60日強漲{d['ret60']:+.0f}%"); score+=1
    elif d['ret60'] and d['ret60']<-10: pts.append(f"❌ 60日弱勢{d['ret60']:+.0f}%"); score-=1
    # 族群
    if d['sector_mom'] and d['sector_mom']>0: pts.append(f"✅ 族群強({d['industry']} {d['sector_mom']:+.0f}%)"); score+=1
    elif d['sector_mom'] is not None: pts.append(f"⚠️ 族群弱({d['industry']} {d['sector_mom']:+.0f}%)")
    # 估值
    if d['pe_pctl'] is not None:
        if d['pe_pctl']<30: pts.append(f"✅ 本益比在3年低檔({d['pe_pctl']:.0f}%位階)"); score+=1
        elif d['pe_pctl']>80: pts.append(f"⚠️ 本益比偏貴({d['pe_pctl']:.0f}%位階)"); score-=1
        else: pts.append(f"➖ 本益比中性({d['pe_pctl']:.0f}%位階)")
    elif d['pe'] is None: pts.append("⚠️ 虧損(無本益比)")
    # 位置
    if d['from_high']>-10: pts.append(f"⚠️ 距52週高僅{d['from_high']:.0f}%(追高風險)")
    elif d['from_high']<-30: pts.append(f"➖ 距52週高{d['from_high']:.0f}%(深跌)")
    return pts,score

codes=sys.argv[1:] if len(sys.argv)>1 else ['2330','2454','2603','2882','3037']
print(f"{'='*60}")
print(f"大盤背景 (所有股共用): regime={regime.upper()} | 散戶閘門={gate} (散戶多空比第{rpctl:.0f}百分位)")
print(f"{'='*60}\n")
for code in codes:
    d=diagnose(code)
    if not d: print(f"[{code}] 無資料\n"); continue
    pts,score=verdict(d)
    tag='🟢 可考慮' if score>=2 else '🔴 避開' if score<=-1 else '🟡 中性'
    print(f"【{d['code']} {d['name']}】 收{d['close']:.1f} PE {d['pe'] if d['pe'] else '—'} | 綜合 {tag} (分數{score:+d})")
    for p in pts: print(f"   {p}")
    print()
