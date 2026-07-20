#!/usr/bin/env python3
"""抓 taifex 三大法人台股期貨未平倉 (TXF) 三年落地。
CSV 端点支持日期区间, 一次拉一个月省请求。big5 编码。
"""
import os, time, urllib.request, urllib.parse, datetime

BASE=os.path.dirname(os.path.abspath(__file__))
CACHE=os.path.join(BASE,"data","taifex"); os.makedirs(CACHE,exist_ok=True)
UA={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
START=datetime.date(2022,7,1); END=datetime.date(2026,7,16)

def fetch_range(d0,d1):
    data=urllib.parse.urlencode({"queryStartDate":d0.strftime("%Y/%m/%d"),
        "queryEndDate":d1.strftime("%Y/%m/%d"),"commodityId":"TXF"}).encode()
    url="https://www.taifex.com.tw/cht/3/futContractsDateDown"
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,data=data,headers=UA),timeout=40) as r:
                return r.read().decode("big5",errors="ignore")
        except Exception as e:
            time.sleep(2**a)
    return None

# 逐月抓 (queryEndDate 可跨多日)
d=START; pulled=0
while d<=END:
    # 该月最后一天
    if d.month==12: nxt=datetime.date(d.year+1,1,1)
    else: nxt=datetime.date(d.year,d.month+1,1)
    mend=min(nxt-datetime.timedelta(days=1), END)
    ym=d.strftime("%Y%m"); fp=os.path.join(CACHE,f"{ym}.csv")
    if not os.path.exists(fp):
        csv=fetch_range(d,mend)
        if csv and "臺股期貨" in csv:
            open(fp,"w").write(csv); pulled+=1
            print(f"[{ym}] pulled, {len(csv)} bytes",flush=True)
        else:
            print(f"[{ym}] empty/fail",flush=True)
        time.sleep(1.0)
    d=nxt
print(f"DONE taifex. pulled={pulled} months",flush=True)
