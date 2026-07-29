#!/usr/bin/env python3
"""抓 TWSE MI_QFIIS 全體外資持股比率 + FinMind TaiwanStockShareholding 外資持股比例歷史。
每日落地 data/shareholding/{ds}.json，供 precompute.py 計算外資持股比率趨勢。

欄位：
  TWSE MI_QFIIS（今日全市場）: 外資持股比率、前日異動
  FinMind Shareholding: 外資持股股數/比率歷史（月頻）
"""
import json, os, time, urllib.request, urllib.parse, datetime, glob

BASE = os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
CACHE = os.path.join(BASE, "data", "shareholding"); os.makedirs(CACHE, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

def get_twse(url):
    for a in range(4):
        try:
            return json.loads(urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=25).read().decode())
        except Exception as e:
            time.sleep(3 * (a + 1))
    return None

def get_finmind(dataset, data_id, d0, d1):
    params = {'dataset': dataset, 'data_id': data_id, 'start_date': d0, 'end_date': d1}
    url = 'https://api.finmindtrade.com/api/v4/data?' + urllib.parse.urlencode(params)
    for a in range(4):
        try:
            r = json.loads(urllib.request.urlopen(url, timeout=30).read().decode())
            if r.get('status') == 200:
                return r.get('data', [])
        except Exception as e:
            time.sleep(5 * (a + 1))
    return None

# ── 1. 每日全市場外資持股比率（TWSE MI_QFIIS）──────────────────────
# 找最近有交易日資料的日期
mi_dates = sorted(os.path.basename(f)[:-5] for f in glob.glob("data/mi_index/*.json"))
today_ds = mi_dates[-1] if mi_dates else datetime.date.today().strftime("%Y%m%d")

fp_today = os.path.join(CACHE, f"qfiis_{today_ds}.json")
pulled_today = 0
if not os.path.exists(fp_today):
    url = "https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS?response=json&selectType=ALLBUT0999"
    d = get_twse(url)
    if d and d.get("stat", "").lower() == "ok" and d.get("data"):
        # 整理成 {code: {持股比率, 尚可投資比率}}
        out = {}
        for row in d["data"]:
            if not row or len(row) < 8: continue
            code = row[0].strip()
            if not (code.isdigit() and len(code) == 4): continue
            try:
                held_pct = float(row[7])   # 全體外資及陸資持股比率
                avail_pct = float(row[6])  # 尚可投資比率
            except (ValueError, TypeError):
                held_pct = avail_pct = None
            out[code] = {"held_pct": held_pct, "avail_pct": avail_pct}
        json.dump({"date": today_ds, "stocks": out}, open(fp_today, "w", encoding="utf-8"), ensure_ascii=False)
        pulled_today = len(out)
        print(f"qfiis_{today_ds}.json 寫入 {pulled_today} 檔")
    else:
        print(f"⚠️ QFIIS 今日資料抓取失敗")
else:
    print(f"qfiis_{today_ds}.json 已存在，跳過")

# ── 2. FinMind 外資持股比例歷史（TaiwanStockShareholding，月頻）──────
# 前200大股票的外資持股比率月歷史，供趨勢計算
import backtest as B
days_list = B.days
mc = []
for code, s in B.DD[days_list[-1]]['stocks'].items():
    c = s['close']; sh = B.co.get(code, {}).get('shares')
    if c and sh and code.isdigit() and len(code) == 4:
        mc.append((c * sh, code))
mc.sort(reverse=True)
uni200 = [c for _, c in mc[:200]]

_today = datetime.date.today().strftime('%Y-%m-%d')
_3y_ago = (datetime.date.today() - datetime.timedelta(days=365 * 3)).strftime('%Y-%m-%d')
fp_hist = os.path.join(CACHE, "shareholding_hist.json")

# 只在沒有或超過7天沒更新時重抓（月頻資料不需要天天全量拉）
need_update = True
if os.path.exists(fp_hist):
    mtime = os.path.getmtime(fp_hist)
    age_days = (time.time() - mtime) / 86400
    if age_days < 7:
        need_update = False
        print(f"shareholding_hist.json 最近 {age_days:.1f} 天內更新過，跳過")

if need_update:
    print(f"抓取 {len(uni200)} 檔外資持股歷史 (FinMind)...")
    all_hist = {}
    for i, code in enumerate(uni200):
        rows = get_finmind('TaiwanStockShareholding', code, _3y_ago, _today)
        if rows:
            all_hist[code] = [
                {"date": r["date"],
                 "held_pct": r.get("ForeignInvestmentSharesRatio"),
                 "issued": r.get("NumberOfSharesIssued")}
                for r in rows
            ]
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(uni200)} 完成", flush=True)
        time.sleep(1.5)
    json.dump(all_hist, open(fp_hist, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"shareholding_hist.json 寫入 {len(all_hist)} 檔外資歷史")

print(f"DONE shareholding. pulled_today={pulled_today}")
