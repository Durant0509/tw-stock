#!/usr/bin/env python3
"""解析 data/mi_index/*.json 快取。提供:
- load_company(): code -> {industry, shares}
- industry_to_index(): 產業名 -> 產業指數名
- load_day(date): {'stocks':{code:{close,amount,pe,name}}, 'indices':{idxname:close}}
- trading_days(): 已快取的日期 (升冪)
"""
import json, os, glob, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "data", "mi_index")

def _num(s):
    if s is None: return None
    s = str(s).replace(",", "").strip()
    if s in ("", "-", "--", "N/A"): return None
    try: return float(s)
    except ValueError: return None

def load_company():
    d = json.load(open(os.path.join(BASE, "data", "company_info.json")))
    # 產業別在 t187ap03_L 是「代碼」；用月營收檔補中文名
    rev = json.load(open(os.path.join(BASE, "data", "rev_latest.json")))
    name_by_code = {c["公司代號"]: c["產業別"] for c in rev if c.get("產業別")}
    out = {}
    for c in d:
        code = c.get("公司代號")
        shares = _num(c.get("已發行普通股數或TDR原股發行股數"))
        out[code] = {"industry": name_by_code.get(code), "shares": shares,
                     "name": c.get("公司簡稱")}
    return out

# 已快取檔實際出現過的產業指數全集（新分類）
def industry_to_index(index_names):
    """把 33 個產業名映到 '...類指數'。index_names = 當天可用指數名 set。"""
    m = {}
    def guess(ind):
        for suf in ("工業", "業"):
            if ind.endswith(suf):
                base = ind[:-len(suf)]
                if base + "類指數" in index_names: return base + "類指數"
        if ind + "類指數" in index_names: return ind + "類指數"
        # 特例
        special = {"化學工業": "化學類指數", "半導體業": "半導體類指數",
                   "電腦及週邊設備業": "電腦及週邊設備類指數", "其他": "其他類指數"}
        return special.get(ind)
    return guess

def load_day(date_str):
    fp = os.path.join(CACHE, f"{date_str}.json")
    if not os.path.exists(fp): return None
    d = json.load(open(fp))
    stocks, indices = {}, {}
    for t in d.get("tables", []):
        f = t.get("fields", [])
        if "本益比" in f and "成交金額" in f:          # table 8 個股
            ci = {n: i for i, n in enumerate(f)}
            for r in t["data"]:
                code = r[ci["證券代號"]]
                if not (code.isdigit() and len(code) == 4):  # 只留普通股
                    continue
                stocks[code] = {
                    "name": r[ci["證券名稱"]],
                    "close": _num(r[ci["收盤價"]]),
                    "amount": _num(r[ci["成交金額"]]),
                    "pe": _num(r[ci["本益比"]]),
                }
        elif f == ['指數', '收盤指數', '漲跌(+/-)', '漲跌點數', '漲跌百分比(%)', '特殊處理註記'] \
                or (f and f[0] == '指數' and '收盤指數' in f):
            ci = {n: i for i, n in enumerate(f)}
            for r in t["data"]:
                nm = r[ci["指數"]]
                if "類指數" in nm and "槓桿" not in nm and "反向" not in nm:
                    indices[nm] = _num(r[ci["收盤指數"]])
    return {"stocks": stocks, "indices": indices}

def trading_days():
    days = []
    for fp in glob.glob(os.path.join(CACHE, "*.json")):
        days.append(os.path.basename(fp)[:-5])
    return sorted(days)

if __name__ == "__main__":
    days = trading_days()
    print(f"已快取交易日: {len(days)}  範圍 {days[0] if days else '-'} ~ {days[-1] if days else '-'}")
    if days:
        d = load_day(days[-1])
        print(f"最新日 {days[-1]}: 個股 {len(d['stocks'])} 檔, 產業指數 {len(d['indices'])} 個")
        s = d["stocks"].get("2330")
        print("  2330 台積電:", s)
        co = load_company()
        print(f"公司資料 {len(co)} 檔; 2330:", co.get("2330"))
        g = industry_to_index(set(d["indices"].keys()))
        print("  半導體業 ->", g("半導體業"), "| 航運業 ->", g("航運業"), "| 化學工業 ->", g("化學工業"))
