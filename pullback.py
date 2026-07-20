#!/usr/bin/env python3
"""严格验证「回撤均值回归」edge (波浪验证的副产品)。
防三偏差: ①跨熊市(牛市买低天然赚) ②point-in-time前150(非曾进过) ③分regime。
命题: 个股从近期高点回撤 X% 后进场, fwd日报酬 vs 同期随机基线。
关键: 若只在bull有效 → 是牛市买低不是edge; 若熊市也守 → 真均值回归。
"""
import statistics as st
import backtest as B
days=B.days

FWD=20; PULLBACK=0.15; HIGH_WIN=60   # 从60日高点回撤15%+ 进场

# regime (0050 MA60斜率, 当下判定, 分割调整)
adj=[100.0]
for i in range(1,len(days)): adj.append(adj[-1]*(1+B.adj_ret('0050',days[i-1],days[i])))
def ma(i): seg=adj[max(0,i-60+1):i+1]; return sum(seg)/len(seg)
def regime_at(i):
    if i<80: return 'warmup'
    s=ma(i)/ma(i-20)-1
    return 'bull' if s>0.02 else 'bear' if s<-0.02 else 'range'

def adj_px(code):
    px=[100.0]
    for i in range(1,len(days)): px.append(px[-1]*(1+B.adj_ret(code,days[i-1],days[i])))
    return px

# point-in-time 前150宇宙 (每20日更新)
uni_at={}
for ti in range(0,len(days),20):
    t=days[ti]; mc=[]
    for code,s in B.DD[t]["stocks"].items():
        c=s["close"]; sh=B.co.get(code,{}).get("shares")
        if c and sh and code.isdigit() and len(code)==4: mc.append((c*sh,code))
    mc.sort(reverse=True); uni_at[ti]={c for _,c in mc[:150]}
def uni_for(i): return uni_at[(i//20)*20]

pxcache={}
def gpx(code):
    if code not in pxcache: pxcache[code]=adj_px(code)
    return pxcache[code]

# 扫: 每檔在前150期间, 若从60日高点回撤>15%, 记进场fwd报酬 + regime
sig={'bull':[],'range':[],'bear':[]}
base={'bull':[],'range':[],'bear':[]}
codes=set()
for u in uni_at.values(): codes|=u
for code in codes:
    px=gpx(code)
    for i in range(HIGH_WIN,len(px)-FWD):
        if code not in uni_for(i): continue
        reg=regime_at(i)
        if reg=='warmup': continue
        if px[i]<=0: continue
        r=px[i+FWD]/px[i]-1
        base[reg].append(r)
        hi=max(px[i-HIGH_WIN:i+1])
        if hi>0 and px[i]/hi-1<=-PULLBACK:   # 回撤>15%
            sig[reg].append(r)

print(f"=== 回撤均值回归严格验证 (回撤{int(PULLBACK*100)}% from {HIGH_WIN}日高, fwd{FWD}日) ===")
print(f"point-in-time前150, {len(codes)}檔曾入选\n")
print(f"{'regime':<8}{'回撤进场n':>10}{'进场avg':>10}{'胜率':>7}{'基线avg':>10}{'基线胜率':>9}{'edge':>9}")
print("-"*66)
verdict_pass=0
for reg in ['bull','range','bear']:
    s=sig[reg]; b=base[reg]
    if not s or not b: print(f"{reg:<8} 样本不足"); continue
    sa=st.mean(s)*100; sw=100*sum(1 for x in s if x>0)/len(s)
    ba=st.mean(b)*100; bw=100*sum(1 for x in b if x>0)/len(b)
    edge=sa-ba
    print(f"{reg:<8}{len(s):>10}{sa:>9.2f}%{sw:>6.0f}%{ba:>9.2f}%{bw:>8.0f}%{edge:>8.2f}pp")
    if edge>1.0: verdict_pass+=1

print(f"\n=== 裁决 ===")
print(f"回撤进场勝基线 (edge>1pp) 的 regime 数: {verdict_pass}/3")
be=sig['bear']; bb=base['bear']
if be and bb:
    bear_edge=st.mean(be)*100-st.mean(bb)*100
    print(f"关键: 熊市 edge = {bear_edge:+.2f}pp", end="  ")
    if bear_edge>1: print("→ 🟢 熊市也守, 真均值回归 (非纯牛市买低)")
    elif bear_edge>-2: print("→ 🟡 熊市中性, 主要靠牛/盘整")
    else: print("→ 🔴 熊市反伤, 是牛市买低假象 (接刀风险)")
