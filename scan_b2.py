#!/usr/bin/env python3
"""B2: 逐维度预测力 (IC) + 重新加权。
对每个维度算 IC = corr(维度值, 未来20日报酬), 跨全部前150横截面。
IC>0.02 加重, IC<-0.02 反转, |IC|<0.02 砍掉。特别拆解 动能/距高 在高分端是否陷阱。
"""
import statistics as st, math
import backtest as B
days=B.days
MA_WIN=120; FWD=20; STEP=5

uni_at={}
for ti in range(0,len(days),20):
    t=days[ti]; mc=[]
    for code,s in B.DD[t]["stocks"].items():
        c=s["close"]; sh=B.co.get(code,{}).get("shares")
        if c and sh and code.isdigit() and len(code)==4: mc.append((c*sh,code))
    mc.sort(reverse=True); uni_at[ti]={c for _,c in mc[:150]}
def uni_for(i): return uni_at[(i//20)*20]

pxc={}
def gpx(code):
    if code not in pxc:
        px=[100.0]
        for i in range(1,len(days)): px.append(px[-1]*(1+B.adj_ret(code,days[i-1],days[i])))
        pxc[code]=px
    return pxc[code]
def pe(code,i): s=B.DD[days[i]]['stocks'].get(code); return s['pe'] if s else None
pe_seq_c={}
def pe_pctl(code,i):
    if code not in pe_seq_c:
        pe_seq_c[code]=[pe(code,j) if pe(code,j) and pe(code,j)>0 else None for j in range(len(days))]
    seq=pe_seq_c[code]; now=seq[i]
    if not now: return None
    hist=[x for x in seq[max(0,i-750):i] if x]
    return 100*sum(1 for x in hist if x<now)/len(hist) if len(hist)>=50 else None
def rsi(px,i,n=14):
    if i<n: return 50
    g=l=0
    for k in range(i-n+1,i+1):
        ch=px[k]-px[k-1]; g+=max(ch,0); l+=max(-ch,0)
    return 100 if l==0 else 100-100/(1+(g/n)/(l/n))

# 各维度取值函数 (point-in-time)
def dim_values(code,i):
    px=gpx(code)
    if i<MA_WIN or px[i]<=0 or i+FWD>=len(days): return None
    ma60=sum(px[i-60+1:i+1])/60; ma120=sum(px[i-120+1:i+1])/120
    look=min(252,i); hi=max(px[i-look:i+1])
    ind=B.co.get(code,{}).get('industry'); nm=B.guess(ind) if ind else None
    smom=None
    if nm:
        c1=B.DD[days[i]]['indices'].get(nm); c0=B.DD[days[i-20]]['indices'].get(nm)
        if c1 and c0: smom=c1/c0-1
    fwd=px[i+FWD]/px[i]-1
    return {
      'above_ma60':px[i]/ma60-1, 'above_ma120':px[i]/ma120-1,
      'ret60':px[i]/px[i-60]-1, 'rsi':rsi(px,i), 'sector_mom':smom,
      'pe_pctl':pe_pctl(code,i), 'from_high':px[i]/hi-1,
      'fwd':fwd
    }

# 收集横截面 (每周)
DIMS=['above_ma60','above_ma120','ret60','rsi','sector_mom','pe_pctl','from_high']
data={dm:[] for dm in DIMS}; fwds={dm:[] for dm in DIMS}
print("收集横截面...")
for i in range(MA_WIN,len(days)-FWD,STEP):
    for code in uni_for(i):
        v=dim_values(code,i)
        if not v: continue
        for dm in DIMS:
            if v[dm] is not None:
                data[dm].append(v[dm]); fwds[dm].append(v['fwd'])

def pearson(xs,ys):
    n=len(xs)
    if n<30: return 0
    mx=st.mean(xs);my=st.mean(ys)
    cov=sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    sx=sum((x-mx)**2 for x in xs)**.5; sy=sum((y-my)**2 for y in ys)**.5
    return cov/(sx*sy) if sx>0 and sy>0 else 0

print(f"\n=== 各维度 IC (与未来{FWD}日报酬相关性) ===")
print(f"{'维度':<14}{'IC':>8}{'样本':>8}  裁决")
ic={}
for dm in DIMS:
    r=pearson(data[dm],fwds[dm]); ic[dm]=r
    n=len(data[dm])
    v='🟢加重' if r>0.02 else '🔴反转(高分端是陷阱)' if r<-0.02 else '➖砍掉(无预测力)'
    print(f"{dm:<14}{r:>+8.3f}{n:>8}  {v}")

# 分组验证: 每维度 高值组 vs 低值组 fwd 报酬
print(f"\n=== 各维度 高值组 vs 低值组 未来{FWD}日报酬 ===")
print(f"{'维度':<14}{'高值组':>10}{'低值组':>10}{'高-低':>10}")
for dm in DIMS:
    pairs=sorted(zip(data[dm],fwds[dm]))
    q=len(pairs)//5
    lo=[f for _,f in pairs[:q]]; hi=[f for _,f in pairs[-q:]]
    print(f"{dm:<14}{st.mean(hi)*100:>9.2f}%{st.mean(lo)*100:>9.2f}%{(st.mean(hi)-st.mean(lo))*100:>9.2f}pp")

print(f"\n=== B1病灶验证: 动能/距高在'高分端'是助力还是陷阱? ===")
# from_high 越接近0(追高)未来越差? ret60 越高未来越差?
for dm in ['ret60','from_high','above_ma60']:
    pairs=sorted(zip(data[dm],fwds[dm]))
    q=len(pairs)//5
    top=[f for _,f in pairs[-q:]]  # 该维度最高的20%
    print(f"  {dm} 最高20%组 未来报酬: {st.mean(top)*100:+.2f}% (IC={ic[dm]:+.3f})")
