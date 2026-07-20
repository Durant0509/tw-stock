#!/usr/bin/env python3
"""救动能引擎的 -58% MDD: 用即时风控 (不依赖 regime, 反应快)。
- trailing stop: 个股跌破持有期高点 N% 出场
- vol target: 组合波动放大时降仓
地板 = V1 纯动能 (MDD -58%)。目标: 压 MDD 又保报酬, R/MDD 赢地板。
"""
import math, statistics as st
import backtest as B
days=B.days

def run_engine(trail=None, vol_target=None, vol_win=20):
    """trail: trailing stop % (如0.20); vol_target: 年化波动目标 (如0.30)"""
    start=80; cash=1.0; pos={}; curve=[]; trades=0
    rebal=set(days[start::B.STEP]); port_hist=[]
    for i in range(start,len(days)):
        d=days[i]; dp=days[i-1]
        prev_total=cash+sum(p['val'] for p in pos.values())
        for code in list(pos):
            pos[code]['val']*=(1+B.adj_ret(code,dp,d))
            c=B.cl(code,d)
            if c:
                pos[code]['peak']=max(pos[code].get('peak',c),c)
                # 固定停损
                if pos[code]['entry'] and c/pos[code]['entry']-1<=B.STOP:
                    cash+=pos[code]['val']*(1-B.SELL_C); trades+=1; del pos[code]; continue
                # trailing stop
                if trail and c/pos[code]['peak']-1<=-trail:
                    cash+=pos[code]['val']*(1-B.SELL_C); trades+=1; del pos[code]
        total=cash+sum(p['val'] for p in pos.values())
        if prev_total>0: port_hist.append(total/prev_total-1)
        if d in rebal:
            cand=B.candidates_ma60only(d)
            if cand:
                scored=sorted(cand,key=lambda c:cand[c][1],reverse=True)
                target=set(scored[:B.N])
                # vol targeting: 近 vol_win 组合波动 vs 目标 → 缩放投入比例
                frac=1.0
                if vol_target and len(port_hist)>=vol_win:
                    rv=st.pstdev(port_hist[-vol_win:])*math.sqrt(252)
                    if rv>0: frac=min(1.0, vol_target/rv)   # 只降不加杠杆
                each=(total*frac)/B.N
                for code in list(pos):
                    if code not in target: cash+=pos[code]['val']*(1-B.SELL_C); trades+=1; del pos[code]
                for code in target:
                    cur=pos.get(code,{}).get('val',0); delta=each-cur
                    if delta>0:
                        buy=min(delta,cash); cash-=buy
                        if code in pos: pos[code]['val']+=buy*(1-B.BUY_C)
                        else: pos[code]={'val':buy*(1-B.BUY_C),'entry':B.cl(code,d),'peak':B.cl(code,d)}; trades+=1
                    elif delta<-1e-9: pos[code]['val']+=delta; cash-=delta*(1-B.SELL_C)
        curve.append((d,cash+sum(p['val'] for p in pos.values())))
    return curve,trades

def stats(curve):
    vals=[v for _,v in curve]
    tot=vals[-1]/vals[0]-1; yrs=len(vals)/252; cagr=vals[-1]**(1/yrs)-1
    peak=vals[0]; mdd=0
    for v in vals: peak=max(peak,v); mdd=min(mdd,v/peak-1)
    return tot,cagr,mdd,cagr/abs(mdd) if mdd else 0

configs=[
    ("V1纯动能(地板)", {}),
    ("trail 25%", {'trail':0.25}),
    ("trail 20%", {'trail':0.20}),
    ("trail 15%", {'trail':0.15}),
    ("vol target 30%", {'vol_target':0.30}),
    ("vol target 25%", {'vol_target':0.25}),
    ("trail20+vol30", {'trail':0.20,'vol_target':0.30}),
]
res={}
for label,kw in configs:
    print(f"跑 {label}...")
    res[label]=run_engine(**kw)

z=B.bench_0050(); zt,zcg,zm,zr=stats(z)
print(f"\n=== 即时风控救引擎 ({days[80]}~{days[-1]}) ===")
print(f"{'配置':<18}{'总报酬':>10}{'CAGR':>8}{'MDD':>9}{'R/MDD':>8}{'交易':>8}")
floor=stats(res['V1纯动能(地板)'][0])
for label,(c,tr) in res.items():
    t,cg,m,r=stats(c)
    print(f"{label:<18}{t*100:>9.0f}%{cg*100:>7.1f}%{m*100:>8.1f}%{r:>8.2f}{tr:>8}")
print(f"{'0050 B&H':<18}{zt*100:>9.0f}%{zcg*100:>7.1f}%{zm*100:>8.1f}%{zr:>8.2f}")

print(f"\n=== 裁决 (P7: R/MDD 赢地板 {floor[3]:.2f}; 理想: MDD压向0050 -36%) ===")
best=None
for label,(c,tr) in res.items():
    if '地板' in label: continue
    t,cg,m,r=stats(c)
    dmdd=m-floor[2]; dret=(t-floor[0])*100; dr=r-floor[3]
    tag="🟢 赢地板" if dr>0.05 else "🔴 没用"
    print(f"  {label:<16} ΔMDD {dmdd:+5.1f}pp | Δ报酬 {dret:+5.0f}pp | R/MDD {r:.2f} ({dr:+.2f}) {tag}")
    if dr>0.05 and (best is None or r>best[1]): best=(label,r,m,t)
if best:
    print(f"\n  🏆 最佳: {best[0]} — R/MDD {best[1]:.2f}, MDD {best[2]*100:.0f}%, 报酬 {best[3]*100:.0f}%")
    print(f"     vs 0050 R/MDD {zr:.2f} → {'✅ 赢0050风险调整' if best[1]>zr else '🔴 仍输0050风险调整'}")
else:
    print(f"\n  🔴 全部即时风控都没赢地板 → 引擎的-58%MDD无解, 结构性问题")
