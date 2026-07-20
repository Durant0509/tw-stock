#!/usr/bin/env python3
"""抓 TWSE MI_MARGN 融资融券 (个股层级) 三年落地。resumable。"""
import json, os, time, urllib.request, datetime

BASE=os.path.dirname(os.path.abspath(__file__))
CACHE=os.path.join(BASE,"data","margin"); os.makedirs(CACHE,exist_ok=True)
UA={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
START=datetime.date(2022,7,1); END=datetime.date(2026,7,16)

def fetch(ds):
    url=f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={ds}&selectType=ALL&response=json"
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            time.sleep(2**a)
    return None

d=START; pulled=skipped=holiday=0
while d<=END:
    if d.weekday()<5:
        ds=d.strftime("%Y%m%d"); fp=os.path.join(CACHE,f"{ds}.json")
        if os.path.exists(fp): skipped+=1
        else:
            js=fetch(ds)
            if js and js.get("stat","").lower()=="ok" and js.get("tables"):
                json.dump(js,open(fp,"w", encoding='utf-8'),ensure_ascii=False); pulled+=1
                if pulled%40==0: print(f"[{ds}] pulled={pulled}",flush=True)
            else: holiday+=1
            time.sleep(0.9)
    d+=datetime.timedelta(days=1)
print(f"DONE margin. pulled={pulled} skipped={skipped} holiday={holiday}",flush=True)
