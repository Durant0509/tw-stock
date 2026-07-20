#!/usr/bin/env python3
"""预运算前150檔诊断 → JSON, 供网页查表。
定位: 体检+排雷 (非选飙股)。综合分数只用来「排雷」(太低亮红灯), 不排名选股。
"""
import json, glob, os, math
import statistics as st
from collections import defaultdict
import backtest as B
import ls_loader as LS
days=B.days

# 大盘背景
adj=[100.0]
for i in range(1,len(days)): adj.append(adj[-1]*(1+B.adj_ret('0050',days[i-1],days[i])))
def ma_i(i): seg=adj[max(0,i-60+1):i+1]; return sum(seg)/len(seg)
cur=len(days)-1
regime='bull' if ma_i(cur)/ma_i(cur-20)-1>0.02 else 'bear' if ma_i(cur)/ma_i(cur-20)-1<-0.02 else 'range'
inst=[];daily=[]
for f in sorted(glob.glob('data/finmind/inst_*.json')): inst+=json.load(open(f, encoding='utf-8'))
for f in sorted(glob.glob('data/finmind/daily_*.json')): daily+=json.load(open(f, encoding='utf-8'))
ib=defaultdict(lambda:[0,0])
for r in inst: ib[r['date']][0]+=r['long_open_interest_balance_volume']; ib[r['date']][1]+=r['short_open_interest_balance_volume']
ob=defaultdict(float)
for r in daily: ob[r['date']]+=r.get('open_interest',0)
retail={d:(ib[d][1]-ib[d][0])/ob[d] for d in ib if ob.get(d,0)>0}
assert retail, "finmind资料空! 请先跑 py pull_finmind.py 重抓台指期资料"
vals=sorted(retail.values()); rcur=retail[max(retail)]
rpctl=100*sum(1 for v in rvals if v<rcur)/len(rvals)
p95=rvals[int(len(rvals)*.95)];p90=rvals[int(len(rvals)*.9)];p20=rvals[int(len(rvals)*.2)]
gate='red' if rcur>=p95 else 'orange' if rcur>=p90 else 'green' if rcur<=p20 else 'gray'

def load_bwibbu(ds):
    fp=f'data/bwibbu_{ds}.json'
    if not os.path.exists(fp): return {}
    d=json.load(open(fp, encoding='utf-8')); out={}
    for r in d.get('data',[]):
        try: out[r[0]]={'yield':float(r[3]) if r[3] not in('','-') else None,'pb':float(r[6]) if r[6] not in('','-') else None}
        except: pass
    return out
bwibbu=load_bwibbu(days[-1])

def foreign_streak(code):
    files=sorted(glob.glob('data/t86/*.json'))[-15:]
    if len(files)<5: return None
    streak=0
    for fp in reversed(files):
        d=json.load(open(fp, encoding='utf-8')); row=[r for r in d.get('data',[]) if r and r[0]==code]
        if not row: break
        try: net=float(str(row[0][4]).replace(',',''))
        except: break
        if net>0: streak+=1
        else: break
    return streak

pxc={}
def gpx(code):
    if code not in pxc:
        px=[100.0]
        for i in range(1,len(days)): px.append(px[-1]*(1+B.adj_ret(code,days[i-1],days[i])))
        pxc[code]=px
    return pxc[code]
def rsi(px,n=14):
    if len(px)<n+1: return None
    g=l=0
    for k in range(len(px)-n,len(px)):
        ch=px[k]-px[k-1]; g+=max(ch,0); l+=max(-ch,0)
    return 100 if l==0 else 100-100/(1+(g/n)/(l/n))
def sector_mom(code):
    ind=B.co.get(code,{}).get('industry'); nm=B.guess(ind) if ind else None
    if not nm: return ind,None
    c1=B.DD[days[-1]]['indices'].get(nm);c0=B.DD[days[-21]]['indices'].get(nm)
    return ind,(c1/c0-1) if c1 and c0 else None

m_now,_=LS.margin_day(days[-1])

# 前150宇宙
mc=[]
for code,s in B.DD[days[-1]]['stocks'].items():
    c=s['close']; sh=B.co.get(code,{}).get('shares')
    if c and sh and code.isdigit() and len(code)==4: mc.append((c*sh,code))
mc.sort(reverse=True); uni=[c for _,c in mc[:150]]

def diagnose(code):
    s=B.DD[days[-1]]['stocks'].get(code)
    if not s or not s['close']: return None
    px=gpx(code); close=s['close']; pe=s['pe']
    look=min(252,len(px)); hi52=max(px[-look:])
    ma60=sum(px[-60:])/60; ma120=sum(px[-120:])/120 if len(px)>=120 else None
    ret60=px[-1]/px[-61]-1 if len(px)>61 else None
    rets=[px[i]/px[i-1]-1 for i in range(len(px)-60,len(px))]
    vol=st.pstdev(rets)*math.sqrt(252)*100 if len(rets)>2 else None
    vs=[B.DD[d]['stocks'].get(code,{}).get('amount') for d in days[-20:]]; vs=[v for v in vs if v]
    vol_ratio=(sum(vs[-5:])/5)/(sum(vs)/20) if len(vs)>=20 else None
    pe_hist=[st2['pe'] for d in days[-750:] for st2 in [B.DD[d]['stocks'].get(code)] if st2 and st2['pe'] and st2['pe']>0]
    pe_pctl=100*sum(1 for x in pe_hist if x<pe)/len(pe_hist) if pe and pe>0 and len(pe_hist)>50 else None
    ind,smom=sector_mom(code)
    ratio=None
    if m_now and code in m_now and m_now[code][0]>0: ratio=m_now[code][1]/m_now[code][0]
    bw=bwibbu.get(code,{})
    # 排雷分数: 只用 B2 证明有预测力的(趋势+动能), 且方向=避烂
    riskscore=0
    if px[-1]<ma60: riskscore-=1
    if ma120 and px[-1]<ma120: riskscore-=1
    if ret60 is not None and ret60<-0.1: riskscore-=1
    if pe is None: riskscore-=1
    if smom is not None and smom<-0.03: riskscore-=1
    return {'code':code,'name':s['name'].strip(),'close':round(close,1),'pe':pe,
      'pe_pctl':round(pe_pctl) if pe_pctl is not None else None,
      'from_high':round((px[-1]/hi52-1)*100,1),'above_ma60':round((px[-1]/ma60-1)*100,1),
      'above_ma120':round((px[-1]/ma120-1)*100,1) if ma120 else None,
      'ret60':round(ret60*100,1) if ret60 else None,'vol':round(vol) if vol else None,
      'vol_ratio':round(vol_ratio,1) if vol_ratio else None,'rsi':round(rsi(px)) if rsi(px) else None,
      'industry':ind,'sector_mom':round(smom*100,1) if smom is not None else None,
      'short_ratio':round(ratio,2) if ratio else None,'yield':bw.get('yield'),'pb':bw.get('pb'),
      'fstreak':foreign_streak(code),'riskscore':riskscore}

out={'asof':f"{days[-1][:4]}-{days[-1][4:6]}-{days[-1][6:]}",'regime':regime,
     'gate':gate,'gate_pctl':round(rpctl),'stocks':{}}
for code in uni:
    d=diagnose(code)
    if d: out['stocks'][code]=d
json.dump(out,open('stocks_data.json','w', encoding='utf-8'),ensure_ascii=False)
print(f"预运算完成: {len(out['stocks'])} 檔 | regime={regime} gate={gate}")
