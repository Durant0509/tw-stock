#!/usr/bin/env python3
"""补波浪盲点 #1(多级别) + #2(参数扫描)。
用 3 个 ZigZag 阈值代表小/中/大级别, 每级别重测第3波规则 + 斐波那契地板。
波浪理论若成立, 应至少某级别通过; 若三级别都=随机, 结论更硬。
"""
import statistics as st
import backtest as B
from elliott import zigzag
days=B.days

def adj_px(code):
    px=[100.0]
    for i in range(1,len(days)): px.append(px[-1]*(1+B.adj_ret(code,days[i-1],days[i])))
    return px

# point-in-time 前150宇宙
codes=set()
for ti in range(0,len(days),20):
    t=days[ti]; mc=[]
    for code,s in B.DD[t]["stocks"].items():
        c=s["close"]; sh=B.co.get(code,{}).get("shares")
        if c and sh and code.isdigit() and len(code)==4: mc.append((c*sh,code))
    mc.sort(reverse=True); codes|={c for _,c in mc[:150]}

FWD=20
LEVELS=[(0.03,"小级别3%"),(0.05,"中级别5%"),(0.08,"大级别8%")]
FIB=(0.382,0.618)

print(f"=== 波浪多级别验证 ({len(codes)}檔前150, {days[0]}~{days[-1]}) ===\n")
pxc={c:adj_px(c) for c in codes}

for pct,lname in LEVELS:
    w3_ok=w3_tot=0
    fib_rets=[]; other_rets=[]
    for code in codes:
        px=pxc[code]
        piv=zigzag(px,pct)
        # 第3波规则
        for k in range(len(piv)-5):
            seq=piv[k:k+6]
            if [x[2] for x in seq]==['L','H','L','H','L','H']:
                w1=seq[1][1]-seq[0][1]; w3=seq[3][1]-seq[2][1]; w5=seq[5][1]-seq[4][1]
                if w1>0 and w3>0 and w5>0:
                    w3_tot+=1
                    if w3>=w1 and w3>=w5: w3_ok+=1
        # 斐波那契 vs 其他回撤
        for k in range(len(piv)-2):
            (i0,p0,t0),(i1,p1,t1),(i2,p2,t2)=piv[k],piv[k+1],piv[k+2]
            if t0=='L' and t1=='H' and t2=='L':
                w1=p1-p0
                if w1<=0 or i2+FWD>=len(px) or px[i2]<=0: continue
                retr=(p1-p2)/w1; r=px[i2+FWD]/px[i2]-1
                if FIB[0]<=retr<=FIB[1]: fib_rets.append(r)
                elif 0.1<=retr<1.0: other_rets.append(r)
    w3pct=100*w3_ok/w3_tot if w3_tot else 0
    fa=st.mean(fib_rets)*100 if fib_rets else 0
    oa=st.mean(other_rets)*100 if other_rets else 0
    print(f"【{lname}】")
    print(f"  第3波不是最短: {w3_ok}/{w3_tot} = {w3pct:.0f}% (随机~33%) {'🟢过' if w3pct>45 else '🔴=随机'}")
    print(f"  斐波那契进场 {fa:+.2f}% vs 其他回撤 {oa:+.2f}% = {fa-oa:+.2f}pp {'🟢特殊' if fa-oa>2 else '🔴无特殊性'}")
    print()

print("=== 裁决 ===")
print("若三个级别的第3波规则都 ≈33%、斐波那契都无特殊性")
print("→ 多级别盲点已补, 波浪在任何级别都无机械预测力, C级结论成立")
