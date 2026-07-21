#!/usr/bin/env python3
"""抓 TWSE T86 三大法人个股买卖超 三年落地 (外资连买用)。"""
import json, os, time, urllib.request, datetime
BASE=os.path.dirname(os.path.abspath(__file__))
CACHE=os.path.join(BASE,"data","t86"); os.makedirs(CACHE,exist_ok=True)
UA={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
START=datetime.date(2022,7,1); END=datetime.date.today()
def fetch(ds):
    url=f"https://www.twse.com.tw/rwd/zh/fund/T86?date={ds}&selectType=ALLBUT0999&response=json"
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception: time.sleep(2**a)
    return None
d=START; pulled=skipped=holiday=0
while d<=END:
    if d.weekday()<5:
        ds=d.strftime("%Y%m%d"); fp=os.path.join(CACHE,f"{ds}.json")
        if os.path.exists(fp): skipped+=1
        else:
            js=fetch(ds)
            if js and js.get("stat","").lower()=="ok" and js.get("data"):
                json.dump(js,open(fp,"w", encoding='utf-8'),ensure_ascii=False); pulled+=1
                if pulled%40==0: print(f"[{ds}] pulled={pulled}",flush=True)
            else: holiday+=1
            time.sleep(0.9)
    d+=datetime.timedelta(days=1)
print(f"DONE t86. pulled={pulled} skipped={skipped} holiday={holiday}",flush=True)
