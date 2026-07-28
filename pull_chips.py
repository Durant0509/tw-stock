#!/usr/bin/env python3
"""抓「法人筹码快报」资料落地 data/chips/:
- spot: TWSE BFI82U 三大法人「现货」买卖超金额 (日档 {YYYYMMDD}.json)
- fut : FinMind MTX 小台指法人 OI + MTX 全市场 OI (月档, 算散户小台净未平仓)
- opt : FinMind TXO 选择权法人买权/卖权 OI (月档, 算外资买权/卖权 + P/C Ratio)
注: 外资台指期(TX)净未平仓已由 pull_finmind.py 抓 (inst_*.json), 这里不重复。
resumable + 含今天段强制重抓 + 内容比对避免重复覆写。跨平台。
"""
import json, os, time, urllib.request, urllib.parse, datetime

BASE=os.path.dirname(os.path.abspath(__file__))
CACHE=os.path.join(BASE,"data","chips"); os.makedirs(CACHE,exist_ok=True)
UA={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
_today=datetime.date.today()
_today_s=_today.strftime('%Y-%m-%d')

# ========== 1) BFI82U 现货三大法人 (日档, 照 pull_t86 模式) ==========
def fetch_spot(ds):
    url=f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?dayDate={ds}&type=day&response=json"
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=25) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception: time.sleep(2**a)
    return None

def pull_spot():
    d=datetime.date(2022,7,1); pulled=skipped=holiday=0
    while d<=_today:
        if d.weekday()<5:
            ds=d.strftime("%Y%m%d"); fp=os.path.join(CACHE,f"spot_{ds}.json")
            if os.path.exists(fp): skipped+=1
            else:
                js=fetch_spot(ds)
                if js and js.get("stat","").lower()=="ok" and js.get("data"):
                    json.dump(js,open(fp,"w",encoding='utf-8'),ensure_ascii=False); pulled+=1
                    if pulled%40==0: print(f"[spot {ds}] pulled={pulled}",flush=True)
                else: holiday+=1
                time.sleep(0.9)
        d+=datetime.timedelta(days=1)
    print(f"DONE spot(BFI82U). pulled={pulled} skipped={skipped} holiday={holiday}",flush=True)

# ========== 2) FinMind 期货/选择权 (月档, 照 pull_finmind 模式) ==========
def fetch_fm(dataset,data_id,d0,d1):
    params={'dataset':dataset,'data_id':data_id,'start_date':d0,'end_date':d1}
    url='https://api.finmindtrade.com/api/v4/data?'+urllib.parse.urlencode(params)
    for a in range(5):
        try:
            r=json.loads(urllib.request.urlopen(url,timeout=40).read().decode())
            if r.get('status')==200: return r.get('data',[])
            print(f'  status {r.get("status")}: {r.get("msg","")[:50]}',flush=True)
            time.sleep(10*(a+1))
        except Exception as e:
            print(f'  retry ({e})',flush=True); time.sleep(5*(a+1))
    return None

def _periods():
    periods=[('2022-07-01','2022-12-31'),('2023-01-01','2023-06-30'),('2023-07-01','2023-12-31'),
             ('2024-01-01','2024-06-30'),('2024-07-01','2024-12-31'),('2025-01-01','2025-06-30'),
             ('2025-07-01','2025-12-31'),('2026-01-01','2026-06-30'),('2026-07-01',_today_s)]
    for yy in range(2027,_today.year+1):
        periods.append((f'{yy}-01-01',f'{yy}-06-30')); periods.append((f'{yy}-07-01',_today_s))
    return periods

def pull_fm(dataset,data_id,tag):
    """落地档名 {tag}_{YYYY-MM}.json; 含今天段强制重抓 + 内容比对。"""
    for d0,d1 in _periods():
        fp=os.path.join(CACHE,f"{tag}_{d0[:7]}.json")
        is_current = d1==_today_s
        if os.path.exists(fp) and not is_current: continue
        rows=fetch_fm(dataset,data_id,d0,d1)
        if rows is not None:
            new_content=json.dumps(rows)
            if os.path.exists(fp) and open(fp,encoding='utf-8').read()==new_content:
                print(f'[{tag} {d0}] 内容相同, 跳过写入',flush=True)
            else:
                open(fp,"w",encoding='utf-8').write(new_content)
                print(f'[{tag} {d0}] {len(rows)} rows 写入',flush=True)
        time.sleep(8)
    print(f'=== {tag} 完成 ===',flush=True)

if __name__=="__main__":
    pull_spot()
    # MTX 小台法人 OI + MTX 全市场 OI (算散户小台净未平仓)
    pull_fm('TaiwanFuturesInstitutionalInvestors','MTX','mtxinst')
    pull_fm('TaiwanFuturesDaily','MTX','mtxdaily')
    # TXO 选择权法人 OI (算外资买权/卖权 + P/C Ratio)
    pull_fm('TaiwanOptionInstitutionalInvestors','TXO','optinst')
    print('DONE chips',flush=True)
