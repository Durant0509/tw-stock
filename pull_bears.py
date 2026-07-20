#!/usr/bin/env python3
"""補抓 2011 歐債 / 2015 陸股崩 兩個熊市窗口 (各含前85日暖機)."""
import json, os, time, urllib.request, datetime

BASE=os.path.dirname(os.path.abspath(__file__))
CACHE=os.path.join(BASE,"data","mi_index"); os.makedirs(CACHE,exist_ok=True)
UA={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

WINDOWS=[
  (datetime.date(2011,3,1), datetime.date(2012,1,31)),   # 歐債熊 + 暖機
  (datetime.date(2015,2,1), datetime.date(2015,10,31)),  # 陸股崩 + 暖機
]

def fetch(ds):
    url=f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={ds}&type=ALL&response=json"
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            time.sleep(2**a)
    return None

pulled=0; holiday=0; skipped=0
for start,end in WINDOWS:
    d=start
    while d<=end:
        if d.weekday()<5:
            ds=d.strftime("%Y%m%d"); fp=os.path.join(CACHE,f"{ds}.json")
            if os.path.exists(fp): skipped+=1
            else:
                js=fetch(ds)
                if js and js.get("stat","").lower()=="ok" and js.get("tables"):
                    json.dump(js,open(fp,"w"),ensure_ascii=False); pulled+=1
                    if pulled%20==0: print(f"[{ds}] pulled={pulled}",flush=True)
                else: holiday+=1
                time.sleep(0.9)
        d+=datetime.timedelta(days=1)
print(f"DONE. pulled={pulled} skipped={skipped} holiday={holiday}",flush=True)
