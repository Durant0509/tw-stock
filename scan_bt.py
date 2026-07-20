#!/usr/bin/env python3
"""B1: 回测综合评分的预测力。
每周按6维度综合分数排序前150 → 高分组 vs 低分组 vs 等权 vs 0050。
分数有效 <=> 高分组显著赢低分组 + 赢等权。point-in-time, 分割调整, 扣成本。
"""
import statistics as st, math
import backtest as B
import ls_loader as LS
days=B.days
STEP=5; N=15; COST=0.003; MA_WIN=120  # 需120日暖机(年线)

# 融资融券快取
mcache={}
for ds in LS.margin_days():
    m,_=LS.margin_day(ds)
    if m: mcache[ds]=m

# point-in-time 前150
uni_at={}
for ti in range(0,len(days),20):
    t=days[ti]; mc=[]
    for code,s in B.DD[t]["stocks"].items():
        c=s["close"]; sh=B.co.get(code,{}).get("shares")
        if c and sh and code.isdigit() and len(code)==4: mc.append((c*sh,code))
    mc.sort(reverse=True); uni_at[ti]={c for _,c in mc[:150]}
def uni_for(i): return uni_at[(i//20)*20]

# 个股分割调整价快取
pxc={}
def gpx(code):
    if code not in pxc:
        px=[100.0]
        for i in range(1,len(days)): px.append(px[-1]*(1+B.adj_ret(code,days[i-1],days[i])))
        pxc[code]=px
    return pxc[code]

def cl(code,i): s=B.DD[days[i]]['stocks'].get(code); return s['close'] if s else None
def pe(code,i): s=B.DD[days[i]]['stocks'].get(code); return s['pe'] if s else None

def rsi(px,i,n=14):
    if i<n: return 50
    g=l=0
    for k in range(i-n+1,i+1):
        ch=px[k]-px[k-1]; g+=max(ch,0); l+=max(-ch,0)
    if l==0: return 100
    return 100-100/(1+(g/n)/(l/n))

# PE历史位阶(每檔预算太慢, 用滚动近似: 存每檔pe序列)
pe_hist_c={}
def pe_pctl(code,i):
    if code not in pe_hist_c:
        seq=[]
        for j in range(len(days)):
            p=pe(code,j)
            seq.append(p if p and p>0 else None)
        pe_hist_c[code]=seq
    seq=pe_hist_c[code]
    now=seq[i]
    if not now: return None
    hist=[x for x in seq[max(0,i-750):i] if x]
    if len(hist)<50: return None
    return 100*sum(1 for x in hist if x<now)/len(hist)

def score(code,i):
    """6维度综合分数 (point-in-time at day i)"""
    px=gpx(code)
    if i<MA_WIN or px[i]<=0: return None
    sc=0
    ma60=sum(px[i-60+1:i+1])/60; ma120=sum(px[i-120+1:i+1])/120
    # 趋势
    sc+= 1 if px[i]>ma60 else -1
    sc+= 1 if px[i]>ma120 else -1
    # 动能
    ret60=px[i]/px[i-60]-1
    if ret60>0.2: sc+=1
    elif ret60<-0.1: sc-=1
    r=rsi(px,i)
    if r>80: sc-=1
    # 族群
    ind=B.co.get(code,{}).get('industry'); nm=B.guess(ind) if ind else None
    if nm:
        c1=B.DD[days[i]]['indices'].get(nm); c0=B.DD[days[i-20]]['indices'].get(nm)
        if c1 and c0:
            sm=c1/c0-1
            sc+= 1 if sm>0 else (-1 if sm<-0.03 else 0)
    # 估值
    pp=pe_pctl(code,i)
    if pp is not None:
        if pp<30: sc+=1
        elif pp>80: sc-=1
    elif pe(code,i) is None: sc-=1
    # 风险: 距52週高
    look=min(252,i); hi=max(px[i-look:i+1])
    fh=px[i]/hi-1
    if fh>-0.1: sc-=1   # 追高
    return sc

# 回测: 每周选高分/低分组
def run(mode):
    """mode: 'hi'=高分组 'lo'=低分组 'ew'=等权"""
    eq=1.0; hold=[]; curve=[]
    rebal=set(range(MA_WIN,len(days),STEP))
    for i in range(MA_WIN,len(days)):
        d=days[i]; dp=days[i-1]
        if hold: eq*=(1+st.mean([B.adj_ret(c,dp,d) for c in hold]))
        if i in rebal:
            uni=uni_for(i)
            if mode=='ew': new=list(uni)[:N] if len(uni)>=N else list(uni)
            else:
                scored=[(c,score(c,i)) for c in uni]
                scored=[(c,s) for c,s in scored if s is not None]
                scored.sort(key=lambda x:x[1],reverse=(mode=='hi'))
                new=[c for c,_ in scored[:N]]
            if set(new)!=set(hold): eq*=(1-COST)
            hold=new
        curve.append((days[i],eq))
    return curve

print("跑 高分组...")
hi=run('hi')
print("跑 低分组...")
lo=run('lo')
print("跑 等权...")
ew=run('ew')

# regime
adj=[100.0]
for i in range(1,len(days)): adj.append(adj[-1]*(1+B.adj_ret('0050',days[i-1],days[i])))
z=[(days[i],adj[i]/adj[MA_WIN]) for i in range(MA_WIN,len(days))]

def stat(curve):
    v=[c[1] for c in curve]; tot=v[-1]/v[0]-1; cagr=(v[-1]/v[0])**(252/len(v))-1
    pk=v[0];mdd=0
    for x in v: pk=max(pk,x);mdd=min(mdd,x/pk-1)
    return tot,cagr,mdd,cagr/abs(mdd) if mdd else 0

print(f"\n=== B1: 综合评分预测力 ({days[MA_WIN]}~{days[-1]}) ===")
print(f"{'组别':<12}{'总报酬':>10}{'CAGR':>8}{'MDD':>8}{'C/MDD':>8}")
for nm,cv in [('高分组🟢',hi),('低分组🔴',lo),('等权',ew),('0050',z)]:
    s=stat(cv)
    print(f"{nm:<12}{s[0]*100:>9.0f}%{s[1]*100:>7.1f}%{s[2]*100:>7.0f}%{s[3]:>8.2f}")

hs=stat(hi); ls=stat(lo); es=stat(ew)
print(f"\n=== 裁决 ===")
print(f"高分-低分: {(hs[0]-ls[0])*100:+.0f}pp | 高分-等权: {(hs[0]-es[0])*100:+.0f}pp")
if hs[0]>ls[0] and hs[0]>es[0]: print("  🟢 评分有预测力: 高分赢低分且赢等权")
elif hs[0]>ls[0]: print("  🟡 高分赢低分(排序有效)但没赢等权(选股未加值)")
else: print("  🔴 评分无预测力: 高分没赢低分")
