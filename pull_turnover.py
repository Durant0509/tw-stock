#!/usr/bin/env python3
"""抓 TWSE FMSRFK_ALL 月周轉率 + BWIBBU_ALL 每日全市場PE/PB/殖利率歷史。
- FMSRFK_ALL: 每月更新，存 data/turnover/YYYYMM.json
- BWIBBU_ALL: 每日更新，存 data/bwibbu_hist/{ds}.json（建立歷史序列）
"""
import json, os, time, urllib.request, glob, datetime

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

def get(url):
    for a in range(4):
        try:
            return json.loads(urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=25).read().decode())
        except Exception as e:
            time.sleep(3 * (a + 1))
    return None

# ── 1. 月周轉率 FMSRFK_ALL ─────────────────────────────────────────
os.makedirs("data/turnover", exist_ok=True)
d = get("https://openapi.twse.com.tw/v1/exchangeReport/FMSRFK_ALL")
if d:
    # 依月份分組存檔
    by_month = {}
    for row in d:
        ym = row.get("Month", "")[:6]  # 取前6碼 YYYYMM（民國年）
        if ym: by_month.setdefault(ym, []).append(row)
    for ym, rows in by_month.items():
        fp = f"data/turnover/{ym}.json"
        new = json.dumps(rows, ensure_ascii=False)
        if not (os.path.exists(fp) and open(fp, encoding="utf-8").read() == new):
            open(fp, "w", encoding="utf-8").write(new)
    latest_ym = max(by_month.keys()) if by_month else "?"
    total = sum(len(v) for v in by_month.values())
    print(f"turnover 更新完成: {len(by_month)} 個月, {total} 筆, 最新月份={latest_ym}")
else:
    print("⚠️ FMSRFK_ALL 抓取失敗")

# ── 2. BWIBBU_ALL 每日全市場 PE/PB/殖利率（建立歷史序列）──────────────
os.makedirs("data/bwibbu_hist", exist_ok=True)

# 找最近交易日（從 mi_index 目錄取）
mi_dates = sorted(os.path.basename(f)[:-5] for f in glob.glob("data/mi_index/*.json"))
# 只補最近60個交易日（避免首次執行太慢）
recent_dates = mi_dates[-60:]

pulled = skipped = 0
for ds in recent_dates:
    fp = f"data/bwibbu_hist/{ds}.json"
    if os.path.exists(fp):
        skipped += 1
        continue
    d2 = get(f"https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL")
    if d2:
        # BWIBBU_ALL 不帶日期參數，只返回最新一天
        # 用 Date 欄位判斷是否是這個交易日
        if d2 and d2[0].get("Date"):
            raw_date = d2[0]["Date"]  # 民國年 e.g. "1150727"
            # 轉成西元年 YYYYMMDD
            try:
                roc_y = int(raw_date[:3]); m = raw_date[3:5]; day = raw_date[5:7]
                ad_ds = f"{roc_y+1911}{m}{day}"
            except:
                ad_ds = ds
            fp2 = f"data/bwibbu_hist/{ad_ds}.json"
            if not os.path.exists(fp2):
                # 整理成 {code: {pe, yield, pb}}
                out = {}
                for row in d2:
                    code = row.get("Code", "").strip()
                    if not (code.isdigit() and len(code) == 4): continue
                    def _f(v):
                        try: return float(v) if v not in ('', '-', None) else None
                        except: return None
                    out[code] = {
                        "pe": _f(row.get("PEratio")),
                        "yield": _f(row.get("DividendYield")),
                        "pb": _f(row.get("PBratio"))
                    }
                json.dump({"date": ad_ds, "stocks": out},
                          open(fp2, "w", encoding="utf-8"), ensure_ascii=False)
                pulled += 1
                print(f"bwibbu_hist/{ad_ds}.json 寫入 {len(out)} 檔")
            break   # BWIBBU_ALL 不支援歷史，只能抓今天，抓完就結束
    time.sleep(1)

print(f"bwibbu_hist: pulled={pulled} skipped={skipped}")
print("DONE turnover+bwibbu_hist")
