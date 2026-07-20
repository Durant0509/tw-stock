#!/usr/bin/env python3
"""个股诊断 增强版 (C完善): 加 殖利率/P/B/量能/波动/多层均线/RSI/外资连买。
维度分组: 趋势 | 动能 | 估值 | 筹码 | 量能 | 风险
外资连买(T86)若资料在则加, 否则跳过。
"""
import sys, json, glob, os, math
import statistics as st
from collections import defaultdict
import backtest as B
import ls_loader as LS
days=B.days

# === 大盘背景 ===
adj=[100.0]
for i in range(1,len(days)): adj.append(adj[-1]*(1+B.adj_ret('0050',days[i-1],days[i])))
def ma_i(i): seg=adj[max(0,i-60+1):i+1]; return sum(seg)/len(seg)
cur=len(days)-1
slope=ma_i(cur)/ma_i(cur-20)-1
regime='bull' if slope>0.02 else 'bear' if slope<-0.02 else 'range'
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
p95=rvals[int(len(rvals)*.95)];p90=rvals[int(len(rvals)*.9)];p20=rvals[int(len(rvals)*.2)]
gate='🔴減碼' if rcur>=p95 else '🟠謹慎' if rcur>=p90 else '🟢進場佳' if rcur<=p20 else '⚪正常'

# BWIBBU_d 殖利率/PB 快取 (抓最新日)
def load_bwibbu(ds):
    import urllib.request
    fp=f'data/bwibbu_{ds}.json'
    if os.path.exists(fp): d=json.load(open(fp, encoding='utf-8'))
    else:
        try:
            url=f"https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date={ds}&response=json"
            d=json.loads(urllib.request.urlopen(url,timeout=20).read().decode())
            json.dump(d,open(fp,"w", encoding='utf-8'),ensure_ascii=False)
        except: return {}
    out={}
    for r in d.get('data',[]):
        try: out[r[0]]={'yield':float(r[3]) if r[3] not in('','-') else None,'pb':float(r[6]) if r[6] not in('','-') else None}
        except: pass
    return out
bwibbu=load_bwibbu(days[-1])

# T86 外资连买 (若资料在)
def foreign_streak(code):
    t86dir='data/t86'
    if not os.path.isdir(t86dir): return None
    files=sorted(glob.glob(f'{t86dir}/*.json'))[-15:]  # 近15日
    if len(files)<5: return None
    streak=0
    for fp in reversed(files):
        d=json.load(open(fp, encoding='utf-8'))
        row=[r for r in d.get('data',[]) if r and r[0]==code]
        if not row: break
        try: net=float(str(row[0][4]).replace(',',''))  # 外陸資買賣超
        except: break
        if net>0: streak+=1
        else: break
    return streak

def adj_px(code):
    px=[100.0]
    for i in range(1,len(days)): px.append(px[-1]*(1+B.adj_ret(code,days[i-1],days[i])))
    return px
def vol_series(code):
    return [B.DD[d]['stocks'].get(code,{}).get('amount') for d in days]

def rsi(px,n=14):
    if len(px)<n+1: return None
    gains=[];losses=[]
    for i in range(len(px)-n,len(px)):
        ch=px[i]-px[i-1]
        gains.append(max(ch,0)); losses.append(max(-ch,0))
    ag=sum(gains)/n; al=sum(losses)/n
    if al==0: return 100
    rs=ag/al; return 100-100/(1+rs)

def sector_mom(code):
    ind=B.co.get(code,{}).get('industry')
    if not ind: return None,None
    nm=B.guess(ind)
    if not nm: return ind,None
    c1=B.DD[days[-1]]['indices'].get(nm); c0=B.DD[days[-21]]['indices'].get(nm)
    return ind,(c1/c0-1) if c1 and c0 else None

def diagnose(code):
    s=B.DD[days[-1]]['stocks'].get(code)
    if not s or not s['close']: return None
    px=adj_px(code); close=s['close']; pe=s['pe']
    look=min(252,len(px)); hi52=max(px[-look:])
    ma5=sum(px[-5:])/5; ma20=sum(px[-20:])/20; ma60=sum(px[-60:])/60
    ma120=sum(px[-120:])/120 if len(px)>=120 else None
    ret60=px[-1]/px[-61]-1 if len(px)>61 else None
    ret20=px[-1]/px[-21]-1 if len(px)>21 else None
    # 波动率(年化)
    rets=[px[i]/px[i-1]-1 for i in range(len(px)-60,len(px))]
    vol=st.pstdev(rets)*math.sqrt(252)*100 if len(rets)>2 else None
    # 量能: 近5日均量 vs 近20日
    vs=[v for v in vol_series(code)[-20:] if v]
    vol_ratio=None
    if len(vs)>=20: vol_ratio=(sum(vs[-5:])/5)/(sum(vs)/20)
    # PE位阶
    pe_hist=[st2['pe'] for d in days[-750:] for st2 in [B.DD[d]['stocks'].get(code)] if st2 and st2['pe'] and st2['pe']>0]
    pe_pctl=100*sum(1 for x in pe_hist if x<pe)/len(pe_hist) if pe and pe>0 and len(pe_hist)>50 else None
    ind,smom=sector_mom(code)
    m,_=LS.margin_day(days[-1]); ratio=None
    if m and code in m and m[code][0]>0: ratio=m[code][1]/m[code][0]
    bw=bwibbu.get(code,{})
    return {'code':code,'name':s['name'].strip(),'close':close,'pe':pe,'pe_pctl':pe_pctl,
      'from_high':(px[-1]/hi52-1)*100,'above_ma60':(px[-1]/ma60-1)*100,
      'above_ma20':(px[-1]/ma20-1)*100,'above_ma120':(px[-1]/ma120-1)*100 if ma120 else None,
      'ret60':ret60*100 if ret60 else None,'ret20':ret20*100 if ret20 else None,
      'vol':vol,'vol_ratio':vol_ratio,'rsi':rsi(px),'industry':ind,
      'sector_mom':smom*100 if smom is not None else None,'short_ratio':ratio,
      'yield':bw.get('yield'),'pb':bw.get('pb'),'fstreak':foreign_streak(code)}

def report(d):
    L=[]; score=0
    # 趋势
    t=[]
    t.append(('站上MA60' if d['above_ma60']>0 else '跌破MA60', 1 if d['above_ma60']>0 else -1))
    if d['above_ma120'] is not None:
        t.append(('站上年線' if d['above_ma120']>0 else '跌破年線', 1 if d['above_ma120']>0 else -1))
    # 动能
    mo=[]
    if d['ret60'] is not None:
        if d['ret60']>20: mo.append((f"60日強漲{d['ret60']:+.0f}%",1))
        elif d['ret60']<-10: mo.append((f"60日弱勢{d['ret60']:+.0f}%",-1))
        else: mo.append((f"60日{d['ret60']:+.0f}%",0))
    if d['rsi'] is not None:
        if d['rsi']>80: mo.append((f"RSI {d['rsi']:.0f} 超買",-1))
        elif d['rsi']<30: mo.append((f"RSI {d['rsi']:.0f} 超賣(可能反彈)",0))
        else: mo.append((f"RSI {d['rsi']:.0f}",0))
    # 族群
    sec=[]
    if d['sector_mom'] is not None:
        sec.append((f"{d['industry']} {d['sector_mom']:+.0f}%", 1 if d['sector_mom']>0 else -1 if d['sector_mom']<-3 else 0))
    # 估值
    val=[]
    if d['pe_pctl'] is not None:
        if d['pe_pctl']<30: val.append((f"本益比3年低檔({d['pe_pctl']:.0f}%位階)",1))
        elif d['pe_pctl']>80: val.append((f"本益比偏貴({d['pe_pctl']:.0f}%位階)",-1))
        else: val.append((f"本益比中性({d['pe_pctl']:.0f}%位階)",0))
    elif d['pe'] is None: val.append(("虧損無本益比",-1))
    if d['yield'] is not None and d['yield']>4: val.append((f"殖利率{d['yield']:.1f}%(高息)",1))
    elif d['yield'] is not None: val.append((f"殖利率{d['yield']:.1f}%",0))
    if d['pb'] is not None:
        if d['pb']<1: val.append((f"股價淨值比{d['pb']:.2f}(破淨)",1))
        else: val.append((f"股價淨值比{d['pb']:.1f}",0))
    # 筹码
    chip=[]
    if d['fstreak'] is not None and d['fstreak']>=3: chip.append((f"外資連買{d['fstreak']}日",1))
    elif d['fstreak'] is not None: chip.append((f"外資連買{d['fstreak']}日",0))
    if d['short_ratio'] is not None:
        if d['short_ratio']>0.3: chip.append((f"券資比{d['short_ratio']:.2f}(空方重/軋空機會)",0))
    # 量能
    q=[]
    if d['vol_ratio'] is not None:
        if d['vol_ratio']>1.5: q.append((f"近5日爆量{d['vol_ratio']:.1f}x",0))
        elif d['vol_ratio']<0.6: q.append((f"量縮{d['vol_ratio']:.1f}x",-1))
    # 风险
    risk=[]
    if d['from_high']>-10: risk.append((f"距52週高{d['from_high']:.0f}%(追高風險)",-1))
    elif d['from_high']<-30: risk.append((f"距52週高{d['from_high']:.0f}%(深跌)",0))
    if d['vol'] is not None: risk.append((f"年化波動{d['vol']:.0f}%"+("(高波動)" if d['vol']>50 else ""),0))
    groups=[('趨勢',t),('動能',mo),('族群',sec),('估值',val),('籌碼',chip),('量能',q),('風險',risk)]
    for _,items in groups:
        for txt,sc in items: score+=sc
    return groups,score

codes=sys.argv[1:] if len(sys.argv)>1 else ['2330','2454','2882','2603','1101','2412']
print("="*66)
print(f"大盤背景: regime={regime.upper()} | 散戶閘門={gate}(第{rpctl:.0f}百分位)")
print("="*66)
icon={1:'✅',-1:'❌',0:'➖'}
for code in codes:
    d=diagnose(code)
    if not d: print(f"\n[{code}] 無資料"); continue
    g,score=report(d)
    tag='🟢 可考慮' if score>=3 else '🔴 避開' if score<=-1 else '🟡 中性'
    print(f"\n【{d['code']} {d['name']}】收{d['close']:.1f} | {tag} (分數{score:+d})")
    for gname,items in g:
        if items:
            parts=' · '.join(f"{icon.get(sc,'')}{txt}" for txt,sc in items)
            print(f"  {gname}: {parts}")
