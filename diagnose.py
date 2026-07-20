#!/usr/bin/env python3
"""P3 分布診斷 — 回答: 價值∩動能∩量能∩MA60 的交集每週有幾檔候選?
逐層漏斗計數, 報告 survivor 分布, 判斷能否湊滿目標檔數 N。
不調參、不回測績效, 只看「有沒有肉」。
"""
import statistics as st
import loader as L

N_TARGET   = 12
AMT_MIN    = 1e8          # 日均成交額 > 1億
MA_WIN     = 60
MOM_WIN    = 20
TOP_MKTCAP = 150

def main():
    days = L.trading_days()
    if len(days) < MA_WIN + MOM_WIN + 5:
        print(f"資料不足 ({len(days)} 日), 需 > {MA_WIN+MOM_WIN}"); return
    co = L.load_company()
    # 全載入記憶體
    day_data = {d: L.load_day(d) for d in days}
    idx_names = set()
    for d in days: idx_names |= set(day_data[d]["indices"].keys())
    guess = L.industry_to_index(idx_names)

    def close(code, d):  s=day_data[d]["stocks"].get(code); return s["close"] if s else None
    def amount(code, d): s=day_data[d]["stocks"].get(code); return s["amount"] if s else None
    def pe(code, d):     s=day_data[d]["stocks"].get(code); return s["pe"] if s else None

    # rebalance = 每 5 個交易日 (約每週)
    start = MA_WIN + MOM_WIN
    rebal = days[start::5]
    print(f"=== P3 分布診斷 | rebalance 點 {len(rebal)} 個 ({rebal[0]}~{rebal[-1]}) ===\n")

    funnel = {"universe":[], "vol":[], "hot":[], "cheap":[], "ma60":[]}
    by_year = {}          # year -> [final_count,...]
    for t in rebal:
        ti = days.index(t)
        hist = days[:ti+1]
        # ① universe: top150 市值
        mc = []
        for code, s in day_data[t]["stocks"].items():
            c = s["close"]; sh = co.get(code, {}).get("shares")
            if c and sh: mc.append((c*sh, code))
        mc.sort(reverse=True)
        uni = [code for _, code in mc[:TOP_MKTCAP]]
        funnel["universe"].append(len(uni))

        # ② 量能: 近20日均額 > 1億
        vol = []
        for code in uni:
            amts = [amount(code, d) for d in hist[-MOM_WIN:]]
            amts = [a for a in amts if a]
            if amts and st.mean(amts) > AMT_MIN: vol.append(code)
        funnel["vol"].append(len(vol))

        # ③ 熱門族群: 族群指數20日報酬 > 全族群中位數 (相對動能)
        sret = {}
        for nm in day_data[t]["indices"]:
            c0 = day_data[hist[-MOM_WIN]]["indices"].get(nm)
            c1 = day_data[t]["indices"].get(nm)
            if c0 and c1: sret[nm] = c1/c0 - 1
        med_sret = st.median(sret.values()) if sret else 0
        hot = []
        for code in vol:
            ind = co.get(code, {}).get("industry")
            idxnm = guess(ind) if ind else None
            if idxnm and sret.get(idxnm, -9) > med_sret: hot.append(code)
        funnel["hot"].append(len(hot))

        # ④ 便宜: PE < 同族群中位數 (交集內)
        by_sec = {}
        for code in hot:
            ind = co.get(code, {}).get("industry"); p = pe(code, t)
            if ind and p and p > 0: by_sec.setdefault(ind, []).append((code, p))
        cheap = []
        for ind, lst in by_sec.items():
            m = st.median([p for _, p in lst])
            cheap += [code for code, p in lst if p <= m]
        funnel["cheap"].append(len(cheap))

        # ⑤ MA60 過濾: 收盤 > MA60 (防價值陷阱)
        ma = []
        for code in cheap:
            cs = [close(code, d) for d in hist[-MA_WIN:]]
            cs = [c for c in cs if c]
            if len(cs) >= MA_WIN*0.8 and close(code, t) and close(code, t) > st.mean(cs):
                ma.append(code)
        funnel["ma60"].append(len(ma))
        by_year.setdefault(t[:4], []).append(len(ma))

    def rpt(label, arr):
        arr = [x for x in arr if x is not None]
        pct = 100*sum(1 for x in arr if x >= N_TARGET)/len(arr)
        print(f"  {label:14s} 中位 {st.median(arr):5.1f} | 範圍 {min(arr):3d}~{max(arr):3d} "
              f"| ≥{N_TARGET}檔的週佔比 {pct:5.1f}%")
    print("漏斗各層存活檔數分布:")
    rpt("①前150宇宙", funnel["universe"])
    rpt("②量能過濾", funnel["vol"])
    rpt("③熱門族群", funnel["hot"])
    rpt("④估值便宜", funnel["cheap"])
    rpt("⑤MA60防陷阱", funnel["ma60"])
    final = funnel["ma60"]
    ok = 100*sum(1 for x in final if x >= N_TARGET)/len(final)
    print(f"\n最終候選池 ≥ {N_TARGET} 檔的週數佔比 (全期混合): {ok:.0f}%")

    print("\n分年拆解 (揭露 regime 依賴, 別被混合數字誤導):")
    for y in sorted(by_year):
        a = by_year[y]
        pct = 100*sum(1 for x in a if x >= N_TARGET)/len(a)
        bar = "█"*int(st.median(a))
        print(f"  {y}: 中位 {st.median(a):4.1f} 檔 | ≥{N_TARGET}週佔比 {pct:5.1f}% {bar}")
    print("\n【判讀】牛市年 (2024-25) 交集厚 = 有肉; 熊市年 (2022) 薄 = MA60 正確防守 (該空手).")

if __name__ == "__main__":
    main()
