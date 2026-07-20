#!/usr/bin/env python3
"""撿便宜 vs 穩健成長 vs benchmark — 跨 2018-2026 含三真熊。
統一起點 (成長因子需 252日暖機), 分市況 + 三真熊 drawdown + 風險調整後。
裁決標準 (pre-registered): 因子留下 <=> ≥2/3真熊壓低回檔 或 改善全期 R/MDD。
"""
import statistics as st
import backtest as B

days=B.days
# 起點: MA60+MOM20 暖機 = 85 (納入 2018 熊). 成長因子需252日, 2018熊標 n/a.
START_I=85
GROWTH_I=260     # 成長因子有效起點
MA=60; SLOPE=20

# regime (分割調整 0050 MA60 斜率)
adj=[]; v=100.0
for i,d in enumerate(days):
    if i>0: v*=(1+B.adj_ret('0050',days[i-1],d))
    adj.append(v)
def ma(i): seg=adj[max(0,i-MA+1):i+1]; return sum(seg)/len(seg)
regime={}
for i in range(len(days)):
    regime[days[i]] = ('warmup' if i<MA+SLOPE else
        'bull' if ma(i)/ma(i-SLOPE)-1>0.02 else 'bear' if ma(i)/ma(i-SLOPE)-1<-0.02 else 'range')

# 三個真熊窗口 (交易日字串範圍)
BEARS={
  "2018貿易戰": ("20181001","20190103"),
  "2020_COVID": ("20200120","20200323"),
  "2022升息熊": ("20220101","20221025"),
}

def run_from(cand_fn,wv,wm,start_i=START_I):
    """複製 backtest.run 但從 start_i 起, 回傳 {date:value}"""
    cash=1.0; pos={}; curve={}
    rebal=set(days[start_i::B.STEP])
    for i in range(start_i,len(days)):
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
        curve[d]=cash+sum(p['val'] for p in pos.values())
    return curve

def bench(code_fn):
    v=1.0; curve={}
    for i in range(START_I,len(days)):
        v*=(1+code_fn(days[i-1],days[i])); curve[days[i]]=v
    return curve

print("跑 只有MA60 (地板)..."); floor=run_from(B.candidates_ma60only,0.0,1.0)
print("跑 撿便宜..."); cheap=run_from(B.candidates,0.5,0.5)
print("跑 穩健成長 (2019起,需暖機)..."); growth=run_from(B.candidates_growth,0.5,0.5,GROWTH_I)
z=bench(lambda a,b:B.adj_ret('0050',a,b))

def window_stats(curve,d0,d1):
    ds=[d for d in sorted(curve) if d0<=d<=d1]
    if len(ds)<2: return None
    vals=[curve[d] for d in ds]
    ret=vals[-1]/vals[0]-1
    peak=vals[0]; mdd=0
    for x in vals: peak=max(peak,x); mdd=min(mdd,x/peak-1)
    return ret*100,mdd*100

def full_stats(curve):
    ds=sorted(curve); vals=[curve[d] for d in ds]
    tot=vals[-1]/vals[0]-1; yrs=len(vals)/252; cagr=vals[-1]**(1/yrs)-1
    peak=vals[0]; mdd=0
    for x in vals: peak=max(peak,x); mdd=min(mdd,x/peak-1)
    return tot*100,cagr*100,mdd*100,cagr/abs(mdd) if mdd else 0

series=[("只有MA60",floor),("撿便宜",cheap),("穩健成長",growth),("0050",z)]

print(f"\n=== 全期對照 (撿便宜/MA60 從 {days[START_I]}; 成長從 {days[GROWTH_I]}) ===")
print(f"{'策略':<10}{'總報酬':>10}{'CAGR':>8}{'MDD':>8}{'R/MDD':>8}")
for name,c in series:
    t,cg,m,r=full_stats(c)
    print(f"{name:<10}{t:>9.0f}%{cg:>7.1f}%{m:>7.1f}%{r:>8.2f}")

print(f"\n=== 三真熊 drawdown 對照 ===")
print(f"{'熊市':<12}{'只有MA60':>16}{'撿便宜':>16}{'穩健成長':>16}{'0050':>16}")
for bn,(d0,d1) in BEARS.items():
    row=f"{bn:<12}"
    for name,c in series:
        s=window_stats(c,d0,d1)
        row+=f"{(f'{s[0]:+.0f}%/{s[1]:.0f}%' if s else 'n/a'):>16}"
    print(row)

print(f"\n=== 🔑 因子歸因: 加了估值篩選, 比『只有MA60』更抗跌嗎? ===")
for bn,(d0,d1) in BEARS.items():
    f_s=window_stats(floor,d0,d1)
    if not f_s: continue
    print(f"  {bn} (只有MA60 MDD {f_s[1]:.0f}%):")
    for name,c in [("撿便宜",cheap),("穩健成長",growth)]:
        s=window_stats(c,d0,d1)
        if s:
            delta=s[1]-f_s[1]  # 正=比地板更抗跌
            tag="✅ 估值加分" if delta>2 else "≈ 無差異" if abs(delta)<=2 else "🔴 估值反傷"
            print(f"    {name}: MDD {s[1]:.0f}% (vs地板 {delta:+.0f}pp) {tag}")
        else:
            print(f"    {name}: n/a (暖機不足)")

print(f"\n=== 裁決 ===")
fr=full_stats(floor)[3]
for name,c in [("撿便宜",cheap),("穩健成長",growth)]:
    beats_floor=0; tested=0
    for bn,(d0,d1) in BEARS.items():
        f_s=window_stats(floor,d0,d1); s=window_stats(c,d0,d1)
        if s and f_s:
            tested+=1
            if s[1]>f_s[1]+2: beats_floor+=1
    r=full_stats(c)[3]
    print(f"  {name}: 熊市贏過『只有MA60』{beats_floor}/{tested} | R/MDD {r:.2f} (地板 {fr:.2f})")
    if beats_floor>=2: print(f"    → ✅ 估值因子有獨立抗跌貢獻, 值得留")
    elif beats_floor==0: print(f"    → 🔴 抗跌全來自MA60, 估值因子多餘 → 可砍, 策略簡化為 族群動能+MA60")
    else: print(f"    → 🟡 證據不足, 需補更多熊市")
