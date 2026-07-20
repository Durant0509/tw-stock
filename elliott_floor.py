#!/usr/bin/env python3
"""波浪理論地板對照: 斐波那契回撤 vs 其他回撤幅度。
隔離「買低」效應——若各回撤區間報酬都差不多, 則斐波那契無特殊性 (純均值回歸)。
消除倖存者偏差: 掃全宇宙 (前150), 不只明星股。
"""
import statistics as st
import backtest as B
from elliott import zigzag
days=B.days

# 回撤區間桶 (第2波回撤第1波的比例)
BUCKETS=[(0.10,0.236,"淺0.10-0.236"),(0.236,0.382,"0.236-0.382"),
         (0.382,0.618,"斐波那契0.382-0.618★"),(0.618,0.786,"0.618-0.786"),
         (0.786,1.0,"深0.786-1.0")]
FWD=20

def adj_px(code):
    px=[100.0]
    for i in range(1,len(days)):
        px.append(px[-1]*(1+B.adj_ret(code,days[i-1],days[i])))
    return px

# 全宇宙: 掃每個 rebalance 日的前150, 收集出現過的 code
universe=set()
for t in days[::20]:
    mc=[]
    for code,s in B.DD[t]["stocks"].items():
        c=s["close"]; sh=B.co.get(code,{}).get("shares")
        if c and sh and code.isdigit() and len(code)==4: mc.append((c*sh,code))
    mc.sort(reverse=True); universe|={c for _,c in mc[:150]}
print(f"全宇宙 {len(universe)} 檔 (含曾進前150者, 反倖存者偏差)\n")

bucket_rets={b[2]:[] for b in BUCKETS}
base_all=[]
for code in universe:
    px=adj_px(code)
    piv=zigzag(px,0.05)
    for k in range(len(piv)-2):
        (i0,p0,t0),(i1,p1,t1),(i2,p2,t2)=piv[k],piv[k+1],piv[k+2]
        if t0=='L' and t1=='H' and t2=='L':
            w1=p1-p0
            if w1<=0: continue
            retr=(p1-p2)/w1
            if i2+FWD<len(px) and px[i2]>0:
                r=px[i2+FWD]/px[i2]-1
                for lo,hi,name in BUCKETS:
                    if lo<=retr<hi: bucket_rets[name].append(r); break
    # 隨機基線
    for i in range(0,len(px)-FWD,10):
        if px[i]>0: base_all.append(px[i+FWD]/px[i]-1)

print(f"{'回撤區間':<22}{'n':>6}{'avg報酬':>10}{'勝率':>8}")
print("-"*48)
for lo,hi,name in BUCKETS:
    r=bucket_rets[name]
    if r:
        avg=st.mean(r)*100; win=100*sum(1 for x in r if x>0)/len(r)
        print(f"{name:<22}{len(r):>6}{avg:>9.2f}%{win:>7.0f}%")
ba=st.mean(base_all)*100; bw=100*sum(1 for x in base_all if x>0)/len(base_all)
print(f"{'隨機基線(任意日)':<22}{len(base_all):>6}{ba:>9.2f}%{bw:>7.0f}%")

# 裁決
fib=st.mean(bucket_rets["斐波那契0.382-0.618★"])*100 if bucket_rets["斐波那契0.382-0.618★"] else 0
others=[]
for lo,hi,name in BUCKETS:
    if "斐波那契" not in name and bucket_rets[name]: others+=bucket_rets[name]
oavg=st.mean(others)*100 if others else 0
print(f"\n=== 裁決: 斐波那契是否比其他回撤幅度特殊? ===")
print(f"  斐波那契區間 avg: {fib:+.2f}%")
print(f"  其他回撤區間 avg: {oavg:+.2f}%")
print(f"  隨機基線 avg:     {ba:+.2f}%")
print(f"  斐波那契 vs 其他回撤: {fib-oavg:+.2f}pp")
print(f"  斐波那契 vs 隨機基線: {fib-ba:+.2f}pp")
if fib-oavg>2: print("  🟢 斐波那契顯著勝其他回撤 → 波浪比例真有特殊性")
elif fib-ba>2 and abs(fib-oavg)<=2: print("  🟡 回撤都賺(買低效應), 但斐波那契不比其他回撤特殊 → 是均值回歸非波浪")
else: print("  🔴 斐波那契無特殊性, 波浪比例是噪音 (C級)")
