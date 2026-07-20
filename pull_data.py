#!/usr/bin/env python3
"""拉 TWSE MI_INDEX 每日全市場資料 (含個股量價PE + 產業指數) 落地快取。
resumable: 已存在的日檔跳過。禮貌速率 + backoff。
"""
import json, os, time, urllib.request, datetime, sys

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "data", "mi_index")
os.makedirs(CACHE, exist_ok=True)

START = datetime.date(2018, 1, 1)    # 補進 2018貿易戰 / 2020 COVID / 2022 升息 三個真熊
END   = datetime.date(2026, 7, 16)   # 到昨天為止
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

def fetch(date_str):
    url = (f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
           f"?date={date_str}&type=ALL&response=json")
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            wait = 2 ** attempt
            print(f"  retry {date_str} ({e}) wait {wait}s", flush=True)
            time.sleep(wait)
    return None

def main():
    d = START
    total = 0; pulled = 0; holiday = 0; skipped = 0
    while d <= END:
        total += 1
        if d.weekday() >= 5:            # 六日跳過
            d += datetime.timedelta(days=1); continue
        ds = d.strftime("%Y%m%d")
        fp = os.path.join(CACHE, f"{ds}.json")
        if os.path.exists(fp):
            skipped += 1; d += datetime.timedelta(days=1); continue
        js = fetch(ds)
        if js and js.get("stat", "").lower() == "ok" and js.get("tables"):
            with open(fp, "w") as f:
                json.dump(js, f, ensure_ascii=False)
            pulled += 1
            if pulled % 20 == 0:
                print(f"[{ds}] pulled={pulled} skipped={skipped} holiday={holiday}", flush=True)
        else:
            holiday += 1                # 假日/無資料 (不寫檔)
        time.sleep(0.9)
        d += datetime.timedelta(days=1)
    print(f"DONE. pulled={pulled} skipped(cached)={skipped} holiday/empty={holiday}", flush=True)

if __name__ == "__main__":
    main()
