#!/usr/bin/env python3
"""用 FinMind 补台指期三年资料 (取代被反爬挡的 taifex):
- TaiwanFuturesInstitutionalInvestors: 三大法人未平仓 (算法人多空)
- TaiwanFuturesDaily: 台指期总未平仓 (算全市场)
FinMind 免费 API 有速率限,分段抓 + 落地。
"""
import urllib.request, urllib.parse, json, time, os

BASE=os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(BASE,"data","finmind"),exist_ok=True)

def fetch(dataset,d0,d1,data_id='TX'):
    params={'dataset':dataset,'data_id':data_id,'start_date':d0,'end_date':d1}
    url='https://api.finmindtrade.com/api/v4/data?'+urllib.parse.urlencode(params)
    for a in range(5):
        try:
            r=json.loads(urllib.request.urlopen(url,timeout=40).read().decode())
            if r.get('status')==200: return r.get('data',[])
            print(f'  status {r.get("status")}: {r.get("msg","")[:50]}',flush=True)
            time.sleep(10*(a+1))   # 速率限, 等久一点
        except Exception as e:
            print(f'  retry ({e})',flush=True); time.sleep(5*(a+1))
    return None

# 分半年抓 (避免单次太大 + 速率限)
periods=[('2022-07-01','2022-12-31'),('2023-01-01','2023-06-30'),('2023-07-01','2023-12-31'),
         ('2024-01-01','2024-06-30'),('2024-07-01','2024-12-31'),('2025-01-01','2025-06-30'),
         ('2025-07-01','2025-12-31'),('2026-01-01','2026-07-16')]

for dataset,tag in [('TaiwanFuturesInstitutionalInvestors','inst'),('TaiwanFuturesDaily','daily')]:
    allrows=[]
    for d0,d1 in periods:
        fp=os.path.join(BASE,"data","finmind",f"{tag}_{d0[:7]}.json")
        if os.path.exists(fp):
            allrows+=json.load(open(fp)); continue
        rows=fetch(dataset,d0,d1)
        if rows is not None:
            new_content=json.dumps(rows)
            # 内容比对: 相同不写入 (避免重复覆写)
            if os.path.exists(fp) and open(fp).read()==new_content:
                allrows+=rows; print(f'[{tag} {d0}] 内容相同, 跳过写入',flush=True)
            else:
                open(fp,"w").write(new_content); allrows+=rows
                print(f'[{tag} {d0}] {len(rows)} rows 写入',flush=True)
        time.sleep(8)
    print(f'=== {tag} 共 {len(allrows)} rows ===',flush=True)
print('DONE finmind',flush=True)
