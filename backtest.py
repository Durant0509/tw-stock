#!/usr/bin/env python3
"""價值 × 動能 v0 回測。
- 宇宙: 前150市值 | 濾網: 量能>1億 + 熱門族群 + 便宜(PE<族群中位) + MA60防陷阱
- 評分: value_pctl*wv + mom_pctl*wm, 選 top N 等權, 週rebalance, -10%停損
- 成本: 手續費0.1425% + 證交稅0.3%(賣) + 滑價0.05%/邊
- 分割防護 (T6鐵則): 單日 |報酬|>50% 視為公司行動, 中性化
- Benchmark (P2/R13 三層): 0050 B&H / 前150等權 / 純估值 / 純動能
"""
import statistics as st
import loader as L

N=12; AMT_MIN=1e8; MA_WIN=60; MOM_WIN=20; TOP=150; STOP=-0.10; STEP=5
BUY_C=0.001425+0.0005; SELL_C=0.001425+0.003+0.0005

def _longest_continuous(all_days):
    """取最長連續交易日段 (相鄰間隔>15天視為斷層). 避免 2011/2015 補抓段污染全期回測."""
    import datetime
    def pd(s): return datetime.date(int(s[:4]),int(s[4:6]),int(s[6:]))
    segs=[[all_days[0]]]
    for i in range(1,len(all_days)):
        if (pd(all_days[i])-pd(all_days[i-1])).days>15: segs.append([all_days[i]])
        else: segs[-1].append(all_days[i])
    return max(segs,key=len)

import os
# 預設用主連續段 (2018-2026, 乾淨無斷層); attribution 需全部熊市 → 設 BT_FULL_DAYS=1
if os.environ.get("BT_FULL_DAYS")=="1":
    days=L.trading_days()                     # 全部 (含 2011/2015 補抓段)
else:
    days=_longest_continuous(L.trading_days())# 主連續段 2018-2026
co=L.load_company()
DD={d:L.load_day(d) for d in days}
idx_names=set()
for d in days: idx_names|=set(DD[d]["indices"].keys())
guess=L.industry_to_index(idx_names)

def cl(code,d): s=DD[d]["stocks"].get(code); return s["close"] if s else None
def am(code,d): s=DD[d]["stocks"].get(code); return s["amount"] if s else None
def pe(code,d): s=DD[d]["stocks"].get(code); return s["pe"] if s else None
def eps_ttm(code,d):
    s=DD[d]["stocks"].get(code)
    if s and s["close"] and s["pe"] and s["pe"]>0: return s["close"]/s["pe"]
    return None
def eps_growth(code,d):
    """EPS_ttm YoY 成長 (產值逐年提升). 用 ~252 交易日前對照 point-in-time EPS."""
    ti=days.index(d)
    if ti<252: return None
    now=eps_ttm(code,d); ago=eps_ttm(code,days[ti-252])
    if now and ago and ago>0: return now/ago-1
    return None

def adj_ret(code,d0,d1):
    """分割防護日報酬"""
    a,b=cl(code,d0),cl(code,d1)
    if not a or not b: return 0.0
    r=b/a-1
    return 0.0 if abs(r)>0.5 else r          # 公司行動中性化

def pctl(vals):
    """value->百分位 rank (0..1), 越大越前"""
    srt=sorted(vals); n=len(srt)
    return {v:(i+0.5)/n for i,v in enumerate(srt)} if n else {}

def candidates(t):
    """回傳 {code:(value_score, mom_score)} 通過全濾網者"""
    ti=days.index(t); hist=days[:ti+1]
    # 宇宙 top150
    mc=[]
    for code,s in DD[t]["stocks"].items():
        c=s["close"]; sh=co.get(code,{}).get("shares")
        if c and sh: mc.append((c*sh,code))
    mc.sort(reverse=True); uni=[c for _,c in mc[:TOP]]
    # 量能
    vol=[]
    for code in uni:
        a=[am(code,d) for d in hist[-MOM_WIN:]]; a=[x for x in a if x]
        if a and st.mean(a)>AMT_MIN: vol.append(code)
    # 族群動能
    sret={}
    for nm in DD[t]["indices"]:
        c0=DD[hist[-MOM_WIN]]["indices"].get(nm); c1=DD[t]["indices"].get(nm)
        if c0 and c1: sret[nm]=c1/c0-1
    med=st.median(sret.values()) if sret else 0
    hot=[]
    for code in vol:
        ind=co.get(code,{}).get("industry"); nm=guess(ind) if ind else None
        if nm and sret.get(nm,-9)>med: hot.append((code,sret[nm]))
    # 便宜: PE<族群中位
    bysec={}
    for code,sr in hot:
        ind=co.get(code,{}).get("industry"); p=pe(code,t)
        if ind and p and p>0: bysec.setdefault(ind,[]).append((code,p,sr))
    cheap=[]
    for ind,lst in bysec.items():
        m=st.median([p for _,p,_ in lst])
        cheap+=[(code,p,sr) for code,p,sr in lst if p<=m]
    # MA60 防陷阱
    passed=[]
    for code,p,sr in cheap:
        cs=[cl(code,d) for d in hist[-MA_WIN:]]; cs=[x for x in cs if x]
        if len(cs)>=MA_WIN*0.8 and cl(code,t)>st.mean(cs): passed.append((code,p,sr))
    if not passed: return {}
    # 評分: 便宜 => value 高分 (PE 低 => 高分, 用 -PE 排百分位); 動能 => sret 高分
    vp=pctl([-p for _,p,_ in passed]); mp=pctl([sr for _,_,sr in passed])
    return {code:(vp[-p],mp[sr]) for code,p,sr in passed}

def candidates_ma60only(t):
    """歸因地板: 前150+量能+族群+MA60, 無任何估值/成長篩選.
    若撿便宜/成長贏不過這個, 估值因子是多餘的 (P7)."""
    ti=days.index(t); hist=days[:ti+1]
    mc=[]
    for code,s in DD[t]["stocks"].items():
        c=s["close"]; sh=co.get(code,{}).get("shares")
        if c and sh: mc.append((c*sh,code))
    mc.sort(reverse=True); uni=[c for _,c in mc[:TOP]]
    vol=[]
    for code in uni:
        a=[am(code,d) for d in hist[-MOM_WIN:]]; a=[x for x in a if x]
        if a and st.mean(a)>AMT_MIN: vol.append(code)
    sret={}
    for nm in DD[t]["indices"]:
        c0=DD[hist[-MOM_WIN]]["indices"].get(nm); c1=DD[t]["indices"].get(nm)
        if c0 and c1: sret[nm]=c1/c0-1
    med=st.median(sret.values()) if sret else 0
    picked=[]
    for code in vol:
        ind=co.get(code,{}).get("industry"); nm=guess(ind) if ind else None
        if nm and sret.get(nm,-9)>med:
            cs=[cl(code,d) for d in hist[-MA_WIN:]]; cs=[x for x in cs if x]
            if len(cs)>=MA_WIN*0.8 and cl(code,t)>st.mean(cs):
                picked.append((code,sret[nm]))
    if not picked: return {}
    mp=pctl([sr for _,sr in picked])
    return {code:(0.0,mp[sr]) for code,sr in picked}   # 只有動能分, 無估值分

def candidates_growth(t, pe_cap=40):
    """穩健成長 GARP: 前150+量能+族群+MA60 共用, 選股=EPS逐年成長 且 PE合理(<=cap).
    回傳 {code:(growth_score, mom_score)}"""
    ti=days.index(t); hist=days[:ti+1]
    mc=[]
    for code,s in DD[t]["stocks"].items():
        c=s["close"]; sh=co.get(code,{}).get("shares")
        if c and sh: mc.append((c*sh,code))
    mc.sort(reverse=True); uni=[c for _,c in mc[:TOP]]
    vol=[]
    for code in uni:
        a=[am(code,d) for d in hist[-MOM_WIN:]]; a=[x for x in a if x]
        if a and st.mean(a)>AMT_MIN: vol.append(code)
    sret={}
    for nm in DD[t]["indices"]:
        c0=DD[hist[-MOM_WIN]]["indices"].get(nm); c1=DD[t]["indices"].get(nm)
        if c0 and c1: sret[nm]=c1/c0-1
    med=st.median(sret.values()) if sret else 0
    hot=[]
    for code in vol:
        ind=co.get(code,{}).get("industry"); nm=guess(ind) if ind else None
        if nm and sret.get(nm,-9)>med: hot.append((code,sret[nm]))
    # GARP 選股: EPS YoY 成長 > 0 且 PE 合理 (0<PE<=cap, 不追天價)
    picked=[]
    for code,sr in hot:
        g=eps_growth(code,t); p=pe(code,t)
        if g is not None and g>0 and p and 0<p<=pe_cap:
            # MA60 防陷阱
            cs=[cl(code,d) for d in hist[-MA_WIN:]]; cs=[x for x in cs if x]
            if len(cs)>=MA_WIN*0.8 and cl(code,t)>st.mean(cs):
                picked.append((code,g,sr))
    if not picked: return {}
    gp=pctl([g for _,g,_ in picked]); mp=pctl([sr for _,_,sr in picked])
    return {code:(gp[g],mp[sr]) for code,g,sr in picked}

def run(wv,wm,label,cand_fn=None):
    """回傳 equity 曲線 (list of (date,value)) + 統計. cand_fn 預設撿便宜; 傳入改用其他選股."""
    if cand_fn is None: cand_fn=candidates
    start=MA_WIN+MOM_WIN
    cash=1.0; pos={}   # code->{'val','entry'}
    curve=[]; trades=0; rebal_dates=set(days[start::STEP])
    for i in range(start,len(days)):
        d=days[i]; dp=days[i-1]
        # 日內: 持倉 mark-to-market + 停損
        for code in list(pos):
            pos[code]['val']*=(1+adj_ret(code,dp,d))
            if cl(code,d) and pos[code]['entry'] and cl(code,d)/pos[code]['entry']-1<=STOP:
                cash+=pos[code]['val']*(1-SELL_C); trades+=1; del pos[code]  # 停損出場
        # rebalance
        if d in rebal_dates:
            cand=cand_fn(d)
            if cand:
                scored=sorted(cand,key=lambda c:wv*cand[c][0]+wm*cand[c][1],reverse=True)
                target=set(scored[:N])
                total=cash+sum(p['val'] for p in pos.values())
                tgt_each=total/N
                # 賣出不在 target
                for code in list(pos):
                    if code not in target:
                        cash+=pos[code]['val']*(1-SELL_C); trades+=1; del pos[code]
                # 調整/買進
                for code in target:
                    cur=pos.get(code,{}).get('val',0)
                    delta=tgt_each-cur
                    if delta>0:                      # 買
                        buy=min(delta,cash)
                        if buy>1e-9:
                            cash-=buy;
                            if code in pos: pos[code]['val']+=buy*(1-BUY_C)
                            else: pos[code]={'val':buy*(1-BUY_C),'entry':cl(code,d)};
                            trades+=1
                    elif delta<-1e-9:                # 減
                        pos[code]['val']+=delta; cash-=delta*(1-SELL_C)
        curve.append((d,cash+sum(p['val'] for p in pos.values())))
    return curve,trades

def bench_0050():
    start=MA_WIN+MOM_WIN; v=1.0; curve=[]
    for i in range(start,len(days)):
        v*=(1+adj_ret('0050',days[i-1],days[i])); curve.append((days[i],v))
    return curve

def bench_universe_ew():
    """前150等權, 週rebalance持有"""
    start=MA_WIN+MOM_WIN; v=1.0; curve=[]; hold=[]
    rebal=set(days[start::STEP])
    for i in range(start,len(days)):
        d=days[i]
        if hold:
            r=st.mean([adj_ret(c,days[i-1],d) for c in hold])
            v*=(1+r)
        if d in rebal:
            mc=[]
            for code,s in DD[d]["stocks"].items():
                c=s["close"]; sh=co.get(code,{}).get("shares")
                if c and sh: mc.append((c*sh,code))
            mc.sort(reverse=True); hold=[c for _,c in mc[:TOP]]
        curve.append((d,v))
    return curve

def stats(curve,trades=None):
    vals=[v for _,v in curve]
    tot=vals[-1]/vals[0]-1
    yrs=len(vals)/252
    cagr=vals[-1]**(1/yrs)-1
    peak=vals[0]; mdd=0
    for v in vals:
        peak=max(peak,v); mdd=min(mdd,v/peak-1)
    r2m=cagr/abs(mdd) if mdd else float('inf')
    wk=len([d for d in days[MA_WIN+MOM_WIN:]])/5
    s=f"報酬 {tot*100:+6.1f}% | CAGR {cagr*100:+5.1f}% | MDD {mdd*100:6.1f}% | R/MDD {r2m:4.2f}"
    if trades is not None: s+=f" | 交易 {trades}筆 ({trades/wk:.2f}/週)"
    return s

if __name__=="__main__":
    print(f"=== v0 回測 {days[MA_WIN+MOM_WIN]} ~ {days[-1]} ===\n")
    combined,tc=run(0.5,0.5,"combined")
    val,tv=run(1.0,0.0,"value")
    mom,tm=run(0.0,1.0,"momentum")
    print("【策略】")
    print("  價值×動能 5:5 :", stats(combined,tc))
    print("  純估值        :", stats(val,tv))
    print("  純動能        :", stats(mom,tm))
    print("\n【Benchmark 三層】")
    print("  0050 B&H      :", stats(bench_0050()))
    print("  前150等權 B&H :", stats(bench_universe_ew()))
