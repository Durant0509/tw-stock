#!/usr/bin/env python3
"""解析多空比资料:
- margin: 券资比 (融券余额/融资余额), 大盘加总 + 个股
- large: 散户多空 = 全市场未平仓 - 前十大 (逆向情绪)
"""
import json, os, glob
BASE=os.path.dirname(os.path.abspath(__file__))

def _num(s):
    if s is None: return None
    s=str(s).replace(",","").strip()
    if s in ("","-","--"): return None
    try: return float(s)
    except: return None

def margin_day(ds):
    """回传 {code:(融资余额,融券余额)} + 大盘加总券资比"""
    fp=os.path.join(BASE,"data","margin",f"{ds}.json")
    if not os.path.exists(fp): return None,None
    d=json.load(open(fp))
    t=None
    for tb in d.get("tables",[]):
        if tb.get("fields") and tb["fields"][0]=="代號" and len(tb.get("data",[]))>100:
            t=tb; break
    if not t: return None,None
    out={}; tot_fin=0; tot_short=0
    for r in t["data"]:
        code=r[0]
        if not (code.isdigit() and len(code)==4): continue
        fin=_num(r[6]); short=_num(r[12])   # 融资今余, 融券今余
        if fin is not None and short is not None:
            out[code]=(fin,short); tot_fin+=fin; tot_short+=short
    mkt_ratio=tot_short/tot_fin if tot_fin>0 else None
    return out, mkt_ratio

def margin_days():
    return sorted(os.path.basename(f)[:-5] for f in glob.glob(os.path.join(BASE,"data","margin","*.json")))

def large_series():
    """回传 {date: 散户多空净比} 从 large CSV。
    散户多空 = (全市场未平仓 - 前十大买) - (全市场 - 前十大卖) 的方向, 简化用前十大集中度。
    栏位: [0]日期[1]商品[3]到期月[5]前五大买[6]前五大卖[7]前十大买[8]前十大卖[9]全市场"""
    out={}
    for fp in sorted(glob.glob(os.path.join(BASE,"data","large","*.csv"))):
        raw=open(fp,'rb').read().decode('cp950',errors='ignore')
        for l in raw.split('\n')[1:]:
            c=l.split(',')
            if len(c)<10: continue
            if c[1].strip()!='TX': continue
            exp=c[3].strip()
            if exp not in ('666666','999999'): continue  # 所有契约合计
            date=c[0].strip().replace('/','')
            top10_buy=_num(c[7]); top10_sell=_num(c[8]); total=_num(c[9])
            if total and total>0 and top10_buy is not None and top10_sell is not None:
                # 前十大净多空占比 (大户方向); 散户为反向
                big_net=(top10_buy-top10_sell)/total
                out[date]=big_net
    return out

if __name__=="__main__":
    days=margin_days()
    print(f"margin: {len(days)}天 {days[0]}~{days[-1]}")
    m,ratio=margin_day('20240315')
    print(f"  2024-03-15 个股{len(m)}檔, 大盘券资比 {ratio:.4f}")
    print(f"  2330 (融资,融券): {m.get('2330')}")
    ls=large_series()
    lsd=sorted(ls)
    print(f"large: {len(ls)}天 {lsd[0]}~{lsd[-1]}")
    print(f"  前十大净多空占比样本: {lsd[0]}={ls[lsd[0]]:.3f}, {lsd[-1]}={ls[lsd[-1]]:.3f}")
