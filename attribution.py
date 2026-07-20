#!/usr/bin/env python3
"""因子歸因終局: 撿便宜 vs 只有MA60 地板, 跨 5 個獨立熊市。
逐熊市獨立回測 (各用所在連續段前85日暖機), 解決不連續資料問題。
裁決: 撿便宜在 ≥3/5 熊市贏過『只有MA60』地板 (>2pp) → 通用抗跌因子; 否則只是特定regime工具。
"""
import os
os.environ["BT_FULL_DAYS"]="1"   # attribution 需全部熊市 (2011/2015 含在內), 逐熊獨立處理斷層
import statistics as st
import backtest as B

days=B.days

# 五個獨立熊市 (峰->谷 近似區間)
BEARS={
  "2011歐債":  ("20110801","20111231"),
  "2015陸股崩":("20150601","20150831"),
  "2018貿易戰":("20181001","20190103"),
  "2020COVID": ("20200120","20200323"),
  "2022升息":  ("20220101","20221025"),
}

def _align(d0,d1):
    lo=[x for x in days if x>=d0]; hi=[x for x in days if x<=d1]
    return (lo[0] if lo else None, hi[-1] if hi else None)

def run_window(cand_fn,wv,wm,d0,d1):
    """在 [d0,d1] 跑回測, 需前85日在同一連續段暖機. 回傳 (ret%,mdd%) 或 None."""
    d0,d1=_align(d0,d1)
    if not d0 or not d1: return None
    i0=days.index(d0); i1=days.index(d1)
    if i0<85: return None
    # 確認暖機期連續 (不跨斷層): 檢查 i0-85..i0 日期間隔
    import datetime
    def pd(s): return datetime.date(int(s[:4]),int(s[4:6]),int(s[6:]))
    for j in range(i0-84,i0+1):
        if (pd(days[j])-pd(days[j-1])).days>15: return None  # 暖機跨斷層, 放棄
    cash=1.0; pos={}; vals=[]
    rebal=set(days[i0::B.STEP])
    for i in range(i0,i1+1):
        d=days[i]; dp=days[i-1]
        for code in list(pos):
            pos[code]['val']*=(1+B.adj_ret(code,dp,d))
            c=B.cl(code,d)
            if c and pos[code]['entry'] and c/pos[code]['entry']-1<=B.STOP:
                cash+=pos[code]['val']*(1-B.SELL_C); del pos[code]
        if d in rebal:
            cand=cand_fn(d)
            if cand:
                scored=sorted(cand,key=lambda c:wv*cand[c][0]+wm*cand[c][1],reverse=True)
                target=set(scored[:B.N]); total=cash+sum(p['val'] for p in pos.values())
                each=total/B.N
                for code in list(pos):
                    if code not in target: cash+=pos[code]['val']*(1-B.SELL_C); del pos[code]
                for code in target:
                    cur=pos.get(code,{}).get('val',0); delta=each-cur
                    if delta>0:
                        buy=min(delta,cash); cash-=buy
                        if code in pos: pos[code]['val']+=buy*(1-B.BUY_C)
                        else: pos[code]={'val':buy*(1-B.BUY_C),'entry':B.cl(code,d)}
                    elif delta<-1e-9: pos[code]['val']+=delta; cash-=delta*(1-B.SELL_C)
        vals.append(cash+sum(p['val'] for p in pos.values()))
    if len(vals)<2: return None
    ret=vals[-1]/vals[0]-1; peak=vals[0]; mdd=0
    for x in vals: peak=max(peak,x); mdd=min(mdd,x/peak-1)
    return ret*100,mdd*100

def bench_window(d0,d1):
    d0,d1=_align(d0,d1)
    if not d0 or not d1: return None
    i0=days.index(d0); i1=days.index(d1); v=1.0; vals=[]
    for i in range(i0,i1+1):
        v*=(1+B.adj_ret('0050',days[i-1],days[i])); vals.append(v)
    ret=vals[-1]/vals[0]-1; peak=vals[0]; mdd=0
    for x in vals: peak=max(peak,x); mdd=min(mdd,x/peak-1)
    return ret*100,mdd*100

print("=== 因子歸因: 撿便宜 vs 只有MA60 地板, 跨 5 獨立熊市 ===\n")
print(f"{'熊市':<12}{'只有MA60':>15}{'撿便宜':>15}{'0050':>15}{'估值貢獻':>12}")
print("-"*70)
win=0; tested=0
for bn,(d0,d1) in BEARS.items():
    fl=run_window(B.candidates_ma60only,0.0,1.0,d0,d1)
    ch=run_window(B.candidates,0.5,0.5,d0,d1)
    zz=bench_window(d0,d1)
    def fmt(s): return f"{s[0]:+.0f}%/{s[1]:.0f}%" if s else "n/a"
    contrib=""
    if fl and ch:
        tested+=1; delta=ch[1]-fl[1]  # 正 = 撿便宜比地板更抗跌
        if delta>2: win+=1; contrib=f"✅ {delta:+.0f}pp"
        elif delta<-2: contrib=f"🔴 {delta:+.0f}pp"
        else: contrib=f"≈ {delta:+.0f}pp"
    print(f"{bn:<12}{fmt(fl):>15}{fmt(ch):>15}{fmt(zz):>15}{contrib:>12}")

print(f"\n=== 裁決 ===")
print(f"撿便宜在 {win}/{tested} 個熊市, 估值篩選比『只有MA60』顯著更抗跌 (>2pp)")
if tested==0:
    print("  ⚠️ 無有效熊市樣本 (暖機資料不足)")
elif win>=3:
    print("  ✅ 撿便宜是【通用抗跌因子】, 值得留進策略")
elif win>=1:
    print(f"  🟡 撿便宜只在特定熊市有效 ({win}/{tested}) → 定位為【特定regime工具】, 非通用alpha")
else:
    print("  🔴 撿便宜無獨立抗跌貢獻 → 砍, 策略簡化為【族群動能+MA60】")
