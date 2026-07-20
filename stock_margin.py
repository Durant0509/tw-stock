#!/usr/bin/env python3
"""前150个股融资融券反向指标验证 (三年)。
个股散户情绪代理:
  A. 券资比 = 融券余额/融资余额 (高=空方压力)
  B. 融资变化率 = 融资余额20日增幅 (散户追买程度, 反向看)
命题: 融资暴增(散户FOMO) → 未来报酬低? 券资比极端 → 反向?
point-in-time 前150 + 跨regime。
"""
import statistics as st
import backtest as B
import ls_loader as LS
days=B.days

# 个股价格(分割调整) + fwd报酬
def stock_fwd(code,d,f):
    if d not in day_idx: return None
    i=day_idx[d]
    if i+f>=len(days): return None
    r=1.0
    for j in range(i,i+f):
        r*=(1+B.adj_ret(code,days[j],days[j+1]))
    return r-1
day_idx={d:i for i,d in enumerate(days)}

# 0050 regime
adj=[100.0]
for i in range(1,len(days)): adj.append(adj[-1]*(1+B.adj_ret('0050',days[i-1],days[i])))
def ma(i): seg=adj[max(0,i-60+1):i+1]; return sum(seg)/len(seg)
def regime_at(i):
    if i<80: return 'warmup'
    s=ma(i)/ma(i-20)-1
    return 'bull' if s>0.02 else 'bear' if s<-0.02 else 'range'

# 载入所有 margin 日的个股融资融券
mdays=LS.margin_days()
print(f"载入 {len(mdays)} 天融资融券...")
margin_cache={}
for ds in mdays:
    m,_=LS.margin_day(ds)
    if m: margin_cache[ds]=m   # {code:(融资,融券)}

# point-in-time 前150
uni_at={}
for ti in range(0,len(days),20):
    t=days[ti]; mc=[]
    for code,s in B.DD[t]["stocks"].items():
        c=s["close"]; sh=B.co.get(code,{}).get("shares")
        if c and sh and code.isdigit() and len(code)==4: mc.append((c*sh,code))
    mc.sort(reverse=True); uni_at[ti]={c for _,c in mc[:150]}
def uni_for(i): return uni_at[(i//20)*20]

FWD=20
# 因子A: 券资比横截面分位 (每日在前150内, 券资比最高/最低组的未来报酬)
# 因子B: 融资20日增幅
facA={'bull':{'hi':[],'lo':[]},'range':{'hi':[],'lo':[]},'bear':{'hi':[],'lo':[]}}
facB={'bull':{'hi':[],'lo':[]},'range':{'hi':[],'lo':[]},'bear':{'hi':[],'lo':[]}}

for i in range(20,len(days)-FWD,5):   # 每5日一个横截面
    d=days[i]
    if d not in margin_cache: continue
    reg=regime_at(i)
    if reg=='warmup': continue
    uni=uni_for(i)
    d20=days[i-20]
    m_now=margin_cache[d]; m_old=margin_cache.get(d20,{})
    rows=[]  # (code, 券资比, 融资增幅)
    for code in uni:
        if code not in m_now: continue
        fin,short=m_now[code]
        if fin<=0: continue
        ratio=short/fin
        fin_chg=None
        if code in m_old and m_old[code][0]>0:
            fin_chg=fin/m_old[code][0]-1
        rows.append((code,ratio,fin_chg))
    if len(rows)<20: continue
    # A: 券资比分位
    rows_a=sorted(rows,key=lambda x:x[1])
    n=len(rows_a); q=max(3,n//5)
    for code,_,_ in rows_a[-q:]:   # 券资比最高(空方压力大)
        r=stock_fwd(code,d,FWD)
        if r is not None: facA[reg]['hi'].append(r)
    for code,_,_ in rows_a[:q]:    # 券资比最低
        r=stock_fwd(code,d,FWD)
        if r is not None: facA[reg]['lo'].append(r)
    # B: 融资增幅分位
    rows_b=sorted([x for x in rows if x[2] is not None],key=lambda x:x[2])
    if len(rows_b)>=20:
        q=max(3,len(rows_b)//5)
        for code,_,_ in rows_b[-q:]:  # 融资暴增(散户FOMO)
            r=stock_fwd(code,d,FWD)
            if r is not None: facB[reg]['hi'].append(r)
        for code,_,_ in rows_b[:q]:   # 融资减
            r=stock_fwd(code,d,FWD)
            if r is not None: facB[reg]['lo'].append(r)

def m(x): return st.mean(x)*100 if x else 0
print(f"\n=== 因子A: 券资比 (融券/融资, 高=空方压力) fwd{FWD} ===")
print(f"{'regime':<8}{'券资比高组':>12}{'券资比低组':>12}{'高-低':>10}")
for reg in ['bull','range','bear']:
    hi=facA[reg]['hi']; lo=facA[reg]['lo']
    if hi and lo: print(f"{reg:<8}{m(hi):>11.2f}%{m(lo):>11.2f}%{m(hi)-m(lo):>9.2f}pp")

print(f"\n=== 因子B: 融资20日增幅 (高=散户FOMO追买) fwd{FWD} ===")
print(f"{'regime':<8}{'融资暴增组':>12}{'融资减少组':>12}{'增-减':>10}")
for reg in ['bull','range','bear']:
    hi=facB[reg]['hi']; lo=facB[reg]['lo']
    if hi and lo: print(f"{reg:<8}{m(hi):>11.2f}%{m(lo):>11.2f}%{m(hi)-m(lo):>9.2f}pp")

print("\n=== 裁决 ===")
print("反向指标成立 <=> 融资暴增组(FOMO)未来报酬 < 融资减少组 (B因子负值)")
print("券资比: 高券资比=空方多, 若反向则未来涨(逆向); 若顺势则未来跌")
