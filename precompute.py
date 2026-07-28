#!/usr/bin/env python3
"""预运算前200檔诊断 → stocks_data.json + scan_data.json。
宇宙: 前200大市值, 日均成交<5000萬自動排除 (流動性門檻)。
新增因子: 投信連買/連賣、三大法人合力、月營收YoY、外資±2σ異常、融資斷頭壓力。
"""
import json, glob, os, math
import statistics as st
from collections import defaultdict
import backtest as B
import ls_loader as LS
days=B.days

# ── 大盤背景 ────────────────────────────────────────────────────────
adj=[100.0]
for i in range(1,len(days)): adj.append(adj[-1]*(1+B.adj_ret('0050',days[i-1],days[i])))
def ma_i(i): seg=adj[max(0,i-60+1):i+1]; return sum(seg)/len(seg)
cur=len(days)-1
regime='bull' if ma_i(cur)/ma_i(cur-20)-1>0.02 else 'bear' if ma_i(cur)/ma_i(cur-20)-1<-0.02 else 'range'

# ── 散戶閘門 ────────────────────────────────────────────────────────
inst=[];daily=[]
for f in sorted(glob.glob('data/finmind/inst_*.json')): inst+=json.load(open(f, encoding='utf-8'))
for f in sorted(glob.glob('data/finmind/daily_*.json')): daily+=json.load(open(f, encoding='utf-8'))
ib=defaultdict(lambda:[0,0])
for r in inst: ib[r['date']][0]+=r['long_open_interest_balance_volume']; ib[r['date']][1]+=r['short_open_interest_balance_volume']
ob=defaultdict(float)
for r in daily: ob[r['date']]+=r.get('open_interest',0)
retail={d:(ib[d][1]-ib[d][0])/ob[d] for d in ib if ob.get(d,0)>0}
assert retail, "finmind資料空! 請先跑 py pull_finmind.py"
rvals=sorted(retail.values()); rcur=retail[max(retail)]
rpctl=100*sum(1 for v in rvals if v<rcur)/len(rvals)
p95=rvals[int(len(rvals)*.95)];p90=rvals[int(len(rvals)*.9)];p20=rvals[int(len(rvals)*.2)]
gate='red' if rcur>=p95 else 'orange' if rcur>=p90 else 'green' if rcur<=p20 else 'gray'

# ── 本益比/殖利率/PB ────────────────────────────────────────────────
def load_bwibbu(ds):
    fp=f'data/bwibbu_{ds}.json'
    if not os.path.exists(fp): return {}
    d=json.load(open(fp, encoding='utf-8')); out={}
    for r in d.get('data',[]):
        try: out[r[0]]={'yield':float(r[3]) if r[3] not in('','-') else None,'pb':float(r[6]) if r[6] not in('','-') else None}
        except: pass
    return out
bwibbu=load_bwibbu(days[-1])

# ── 月營收 YoY ──────────────────────────────────────────────────────
rev_map={}
if os.path.exists('data/rev_latest.json'):
    for r in json.load(open('data/rev_latest.json',encoding='utf-8')):
        code=r.get('公司代號','')
        try: yoy=float(r.get('營業收入-去年同月增減(%)') or 'x')
        except: yoy=None
        try: mom=float(r.get('營業收入-上月比較增減(%)') or 'x')
        except: mom=None
        rev_map[code]={'yoy':round(yoy,1) if yoy is not None else None,
                       'mom':round(mom,1) if mom is not None else None,
                       'ym':r.get('資料年月','')}

# ── t86 個股三大法人 (外資/投信/三大合力) 近120日 ────────────────────
_t86_files=sorted(glob.glob('data/t86/*.json'))[-120:]
# {ds: {code: {'f':外資淨, 'tr':投信淨, 'all3':三大法人淨}}}
_t86={}
for _fp in _t86_files:
    _ds=os.path.basename(_fp)[:-5]
    try: _d=json.load(open(_fp,encoding='utf-8'))
    except: continue
    _row={}
    for r in _d.get('data',[]):
        if r and len(r)>18:
            try:
                _row[r[0]]={
                    'f':  float(str(r[4]).replace(',','')),   # 外資淨買超
                    'tr': float(str(r[10]).replace(',','')),  # 投信淨買超
                    'all3':float(str(r[18]).replace(',',''))  # 三大法人合計
                }
            except: pass
    _t86[_ds]=_row
_t86_dates=sorted(_t86)

def _streak(code, field):
    """計算指定欄位的雙向連續天數 (+連買, -連賣)。"""
    if len(_t86_dates)<3: return 0
    streak=0; direction=None
    for ds in reversed(_t86_dates):
        r=_t86[ds].get(code)
        if r is None: break
        v=r.get(field)
        if v is None: break
        if direction is None:
            direction = 1 if v>0 else (-1 if v<0 else 0)
            if direction==0: break
        if (direction==1 and v>0) or (direction==-1 and v<0): streak+=1
        else: break
    return streak*direction if direction else 0

def foreign_streak(code): return _streak(code,'f')
def trust_streak(code):   return _streak(code,'tr')
def all3_streak(code):    return _streak(code,'all3')

def foreign_zscore(code):
    """外資今日買超相對90日均值的 z-score (±2σ判異常)。"""
    vals=[_t86[ds][code]['f'] for ds in _t86_dates[-90:] if code in _t86.get(ds,{}) and _t86[ds][code].get('f') is not None]
    if len(vals)<20: return None
    m=sum(vals)/len(vals); sd=(sum((v-m)**2 for v in vals)/len(vals))**.5
    if sd==0: return None
    return round((vals[-1]-m)/sd,2)

# ── 融資融券 (最新可用日) ────────────────────────────────────────────
# 找最新有個股資料的 margin 檔
m_now=None; m_date=None
for _f in reversed(sorted(glob.glob('data/margin/*.json'))):
    _m,_=LS.margin_day(os.path.basename(_f)[:-5])
    if _m and len(_m)>100:
        m_now=_m; m_date=os.path.basename(_f)[:-5]; break

# 融資斷頭壓力：融資餘額相對近30日歷史的百分位（越高=越多散戶持多、斷頭壓力越大）
def margin_pressure(code):
    """返回 (融資餘額, 融券餘額, 融券/融資比, 融資近30日百分位)。百分位高=散戶擁擠=危險。"""
    if not m_now or code not in m_now: return None,None,None,None
    fin,short=m_now[code]
    ratio=round(short/fin,3) if fin>0 else None
    # 歷史融資餘額百分位
    hist_fin=[]
    for _f in sorted(glob.glob('data/margin/*.json'))[-30:]:
        _m,_=LS.margin_day(os.path.basename(_f)[:-5])
        if _m and code in _m: hist_fin.append(_m[code][0])
    pctl=round(100*sum(1 for v in hist_fin if v<fin)/len(hist_fin)) if len(hist_fin)>=5 else None
    return round(fin), round(short) if short else 0, ratio, pctl

# ── 股價/技術工具 ────────────────────────────────────────────────────
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

def stock_chart(code):
    """個股90日線圖：股價指數化 + 外資買賣超張 + ±2σ閾值。"""
    px=gpx(code)
    if len(px)<90: return None
    seg=px[-90:]; base=seg[0] or 1
    price=[round(v/base*100,1) for v in seg]
    dts=[d[4:6]+'/'+d[6:] for d in days[-90:]]
    fnet=[]
    for ds in _t86_dates[-90:]:
        v=_t86[ds].get(code,{}).get('f')
        fnet.append([ds[4:6]+'/'+ds[6:], round(v/1000) if v is not None else None])
    vals=[x[1] for x in fnet if x[1] is not None]
    thr=None
    if len(vals)>=20:
        m=sum(vals)/len(vals); sd=(sum((v-m)**2 for v in vals)/len(vals))**.5
        thr={'mean':round(m),'hi':round(m+2*sd),'lo':round(m-2*sd)}
    return {'price':[[dts[i],price[i]] for i in range(len(price))],'fnet':fnet,'fthr':thr}

# ── 前200大宇宙（濾掉日均成交<5000萬） ──────────────────────────────
mc=[]
for code,s in B.DD[days[-1]]['stocks'].items():
    c=s['close']; sh=B.co.get(code,{}).get('shares')
    if c and sh and code.isdigit() and len(code)==4:
        mc.append((c*sh,code))
mc.sort(reverse=True)
top200=[c for _,c in mc[:200]]

# 計算日均成交（近20日），過濾流動性不足
def avg_amount(code):
    vs=[B.DD[d]['stocks'].get(code,{}).get('amount') or 0 for d in days[-20:]]
    vs=[v for v in vs if v>0]
    return sum(vs)/len(vs) if vs else 0

uni=[c for c in top200 if avg_amount(c)>=5e7]  # 日均成交≥5000萬
print(f"宇宙: 前200大→流動性篩選後 {len(uni)} 檔 (排除 {200-len(uni)} 檔)")

# ── 個股診斷 ────────────────────────────────────────────────────────
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
    bw=bwibbu.get(code,{})
    _fs=foreign_streak(code)
    _ts=trust_streak(code)
    _a3=all3_streak(code)
    _fz=foreign_zscore(code)
    _fin,_short,_ratio,_fin_pctl=margin_pressure(code)
    rev=rev_map.get(code,{})
    # 排雷分數
    riskscore=0
    if px[-1]<ma60: riskscore-=1
    if ma120 and px[-1]<ma120: riskscore-=1
    if ret60 is not None and ret60<-0.1: riskscore-=1
    if pe is None: riskscore-=1
    if smom is not None and smom<-0.03: riskscore-=1
    if _fs is not None and _fs<=-3: riskscore-=1
    if _ts is not None and _ts<=-3: riskscore-=1   # 投信連賣也是危險訊號
    if _fin_pctl is not None and _fin_pctl>=90: riskscore-=1  # 融資擁擠
    return {
        'code':code,'name':s['name'].strip(),'close':round(close,1),'pe':pe,
        'pe_pctl':round(pe_pctl) if pe_pctl is not None else None,
        'from_high':round((px[-1]/hi52-1)*100,1),
        'above_ma60':round((px[-1]/ma60-1)*100,1),
        'above_ma120':round((px[-1]/ma120-1)*100,1) if ma120 else None,
        'ret60':round(ret60*100,1) if ret60 else None,
        'vol':round(vol) if vol else None,
        'vol_ratio':round(vol_ratio,1) if vol_ratio else None,
        'rsi':round(rsi(px)) if rsi(px) else None,
        'industry':ind,
        'sector_mom':round(smom*100,1) if smom is not None else None,
        'fstreak':_fs,        # 外資連買(+)/連賣(-)天數
        'tstreak':_ts,        # 投信連買(+)/連賣(-)天數
        'a3streak':_a3,       # 三大法人合力連買(+)/連賣(-)天數
        'fzscore':_fz,        # 外資今日 z-score (±2σ異常)
        'fin_bal':_fin,       # 融資餘額(千股)
        'short_bal':_short,   # 融券餘額(千股)
        'short_ratio':_ratio, # 融券/融資比
        'fin_pctl':_fin_pctl, # 融資近30日百分位 (高=擁擠=危險)
        'rev_yoy':rev.get('yoy'),  # 月營收 YoY%
        'rev_mom':rev.get('mom'),  # 月營收 MoM%
        'rev_ym':rev.get('ym',''), # 營收年月
        'yield':bw.get('yield'),'pb':bw.get('pb'),
        'riskscore':riskscore,
        'chart':stock_chart(code)
    }

out={'asof':f"{days[-1][:4]}-{days[-1][4:6]}-{days[-1][6:]}",
     'regime':regime,'gate':gate,'gate_pctl':round(rpctl),'stocks':{}}
for code in uni:
    d=diagnose(code)
    if d: out['stocks'][code]=d
json.dump(out,open('stocks_data.json','w',encoding='utf-8'),ensure_ascii=False)
print(f"預運算完成: {len(out['stocks'])} 檔 | regime={regime} gate={gate} margin_date={m_date}")

# ── 選股雷達評分 ──────────────────────────────────────────────────────
def scan_score(s):
    """
    綜合評分，使用所有可用資料：
    核心：族群動能+MA60（回測驗證最強因子）
    籌碼：外資連買/連賣、投信連買/連賣、三大法人合力、外資±2σ異常大單
    基本面：月營收YoY加速
    風險：融資擁擠（斷頭壓力）、RSI超買、排雷分數
    """
    pts=0; reasons=[]; flags=[]
    sm    = s.get('sector_mom') or 0
    ma60  = s.get('above_ma60') or 0
    vr    = s.get('vol_ratio') or 0
    fs    = s.get('fstreak') or 0
    ts    = s.get('tstreak') or 0
    a3    = s.get('a3streak') or 0
    fz    = s.get('fzscore')           # 可為 None
    rs    = s.get('riskscore') or 0
    rsi_v = s.get('rsi') or 50
    fh    = s.get('from_high') or 0
    yoy   = s.get('rev_yoy')           # 可為 None
    fp    = s.get('fin_pctl')          # 可為 None

    # ① 族群動能（核心，回測驗證最強）
    if sm>=1.5:   pts+=3; reasons.append(f'族群動能強({sm:.1f}%)')
    elif sm>=0.5: pts+=2; reasons.append(f'族群動能正({sm:.1f}%)')
    elif sm>=0:   pts+=1; reasons.append(f'族群動能平({sm:.1f}%)')
    else:         pts-=2; flags.append(f'族群動能弱({sm:.1f}%)')

    # ② MA60站穩
    if ma60>=5:   pts+=2; reasons.append(f'站上MA60 +{ma60:.1f}%')
    elif ma60>=0: pts+=1; reasons.append(f'站上MA60 +{ma60:.1f}%')
    else:         pts-=2; flags.append(f'破MA60 {ma60:.1f}%')

    # ③ 量能
    if vr>=1.3:   pts+=2; reasons.append(f'量能放大 {vr:.1f}×')
    elif vr>=1.0: pts+=1; reasons.append(f'量能正常 {vr:.1f}×')

    # ④ 外資籌碼（連賣≥3日=有效危險訊號，回測驗證）
    if fs>=5:    pts+=3; reasons.append(f'外資連買 {fs}日 ★')
    elif fs>=3:  pts+=2; reasons.append(f'外資連買 {fs}日')
    elif fs>=1:  pts+=1; reasons.append(f'外資買超 {fs}日')
    elif fs<=-5: pts-=4; flags.append(f'外資連賣 {abs(fs)}日 ⚠⚠')
    elif fs<=-3: pts-=3; flags.append(f'外資連賣 {abs(fs)}日 ⚠')
    elif fs<0:   pts-=1; flags.append(f'外資賣超 {abs(fs)}日')

    # ⑤ 投信籌碼（連賣≥3日=危險訊號，加入排雷）
    if ts>=3:    pts+=2; reasons.append(f'投信連買 {ts}日')
    elif ts>=1:  pts+=1; reasons.append(f'投信買超 {ts}日')
    elif ts<=-3: pts-=2; flags.append(f'投信連賣 {abs(ts)}日 ⚠')
    elif ts<0:   pts-=1; flags.append(f'投信賣超 {abs(ts)}日')

    # ⑥ 三大法人合力（外資+投信+自營同向更強）
    if a3>=5:    pts+=2; reasons.append(f'三大合力連買 {a3}日 ★')
    elif a3>=3:  pts+=1; reasons.append(f'三大合力買 {a3}日')
    elif a3<=-3: pts-=2; flags.append(f'三大合力連賣 {abs(a3)}日 ⚠')

    # ⑦ 外資±2σ 異常大買/大賣（單日劇變）
    if fz is not None:
        if fz>=2:   pts+=1; reasons.append(f'外資異常大買(z={fz:.1f})')
        elif fz<=-2: pts-=2; flags.append(f'外資異常大賣(z={fz:.1f}) ⚠')

    # ⑧ 月營收 YoY（基本面動能）
    if yoy is not None:
        if yoy>=50:   pts+=2; reasons.append(f'月營收YoY +{yoy:.0f}% ★')
        elif yoy>=20: pts+=1; reasons.append(f'月營收YoY +{yoy:.0f}%')
        elif yoy<-10: pts-=1; flags.append(f'月營收YoY {yoy:.0f}%')

    # ⑨ 融資擁擠（散戶斷頭壓力）
    if fp is not None:
        if fp>=90:   pts-=2; flags.append(f'融資高位({fp}pctl) 斷頭壓力⚠')
        elif fp>=75: pts-=1; flags.append(f'融資偏高({fp}pctl)')
        elif fp<=20: pts+=1; reasons.append(f'融資低位({fp}pctl) 乾淨')

    # ⑩ 排雷分數（負值=有風險訊號）
    if rs<0: pts+=rs*2; flags.append(f'排雷警示 {abs(rs)}項')

    # ⑪ RSI
    if 45<=rsi_v<=70: pts+=1; reasons.append(f'RSI健康({rsi_v})')
    elif rsi_v>80:    pts-=1; flags.append(f'RSI超買({rsi_v})')
    elif rsi_v<35:    pts-=1; flags.append(f'RSI弱({rsi_v})')

    # ⑫ 距高點甜蜜點
    if -10<=fh<=-2: pts+=1; reasons.append(f'距高甜蜜點({fh:.1f}%)')
    elif fh<-20:    pts-=1; flags.append(f'距高點過遠({fh:.1f}%)')

    return pts, reasons, flags

scan_list=[]
for code,s in out['stocks'].items():
    pts,reasons,flags=scan_score(s)
    scan_list.append({
        'code':s['code'],'name':s['name'],'industry':s.get('industry',''),
        'close':s['close'],'pe':s.get('pe'),'rsi':s.get('rsi'),
        'above_ma60':s.get('above_ma60'),'vol_ratio':s.get('vol_ratio'),
        'sector_mom':s.get('sector_mom'),
        'fstreak':s.get('fstreak'),'tstreak':s.get('tstreak'),'a3streak':s.get('a3streak'),
        'fzscore':s.get('fzscore'),
        'from_high':s.get('from_high'),'riskscore':s.get('riskscore'),
        'fin_pctl':s.get('fin_pctl'),'short_ratio':s.get('short_ratio'),
        'rev_yoy':s.get('rev_yoy'),'rev_ym':s.get('rev_ym',''),
        'pts':pts,'reasons':reasons,'flags':flags
    })
scan_list.sort(key=lambda x:-x['pts'])

scan_out={
    'asof':out['asof'],'regime':regime,'gate':gate,'gate_pctl':round(rpctl),
    'top':scan_list[:20],
    'watch':scan_list[20:50],
    'avoid':[x for x in scan_list if x['pts']<=-6]
}
json.dump(scan_out,open('scan_data.json','w',encoding='utf-8'),ensure_ascii=False)
print(f"選股雷達完成: top={len(scan_out['top'])} watch={len(scan_out['watch'])} avoid={len(scan_out['avoid'])}")
