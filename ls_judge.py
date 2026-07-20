#!/usr/bin/env python3
"""审判两个多空比因子: 券资比 + 散户多空(前十大集中)。
标准同 playbook #10 外资买超: 相关性 + 分组报酬 + 跨regime。
命题: 指标当下值 → 未来 fwd 日大盘(0050)报酬有无预测力?
"""
import statistics as st
import backtest as B
import ls_loader as LS
days=B.days

# 0050 分割调整报酬序列 + regime
adj=[100.0]
for i in range(1,len(days)): adj.append(adj[-1]*(1+B.adj_ret('0050',days[i-1],days[i])))
def fwd_ret(i,f): return adj[i+f]/adj[i]-1 if i+f<len(adj) else None
def ma(i): seg=adj[max(0,i-60+1):i+1]; return sum(seg)/len(seg)
def regime_at(i):
    if i<80: return 'warmup'
    s=ma(i)/ma(i-20)-1
    return 'bull' if s>0.02 else 'bear' if s<-0.02 else 'range'

def pearson(xs,ys):
    n=len(xs)
    if n<10: return 0
    mx=st.mean(xs); my=st.mean(ys)
    cov=sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    sx=sum((x-mx)**2 for x in xs)**.5; sy=sum((y-my)**2 for y in ys)**.5
    return cov/(sx*sy) if sx>0 and sy>0 else 0

# ---- 因子1: 大盘券资比 (每日) ----
print("=== 因子1: 大盘券资比 (融券/融资, 散户空头情绪) ===")
mdays=LS.margin_days()
ratio_by_date={}
for ds in mdays:
    _,r=LS.margin_day(ds)
    if r is not None: ratio_by_date[ds]=r
# 对齐到 days index, 算 券资比 vs fwd20 报酬
FWD=20
for fwd in [5,20]:
    xs=[]; ys=[]
    for i,d in enumerate(days):
        if d in ratio_by_date:
            fr=fwd_ret(i,fwd)
            if fr is not None: xs.append(ratio_by_date[d]); ys.append(fr)
    r=pearson(xs,ys)
    # 分组: 高券资比(空头多) vs 低
    med=st.median(xs)
    hi=[y for x,y in zip(xs,ys) if x>med]; lo=[y for x,y in zip(xs,ys) if x<=med]
    print(f"  fwd{fwd}日: Pearson={r:+.3f} | 高券资比后avg {st.mean(hi)*100:+.2f}% | 低券资比后avg {st.mean(lo)*100:+.2f}%")

# ---- 因子2: 散户多空 (前十大集中度, 逆向) ----
print("\n=== 因子2: 前十大集中净多空 (大户方向, 散户反向) ===")
ls=LS.large_series()
for fwd in [5,20]:
    xs=[]; ys=[]
    for i,d in enumerate(days):
        if d in ls:
            fr=fwd_ret(i,fwd)
            if fr is not None: xs.append(ls[d]); ys.append(fr)
    r=pearson(xs,ys)
    med=st.median(xs)
    hi=[y for x,y in zip(xs,ys) if x>med]; lo=[y for x,y in zip(xs,ys) if x<=med]
    print(f"  fwd{fwd}日: Pearson={r:+.3f} | 大户偏多后avg {st.mean(hi)*100:+.2f}% | 大户偏空后avg {st.mean(lo)*100:+.2f}%")

# ---- 跨 regime 分解 (券资比) ----
print("\n=== 券资比跨regime (fwd20) ===")
for reg in ['bull','range','bear']:
    xs=[]; ys=[]
    for i,d in enumerate(days):
        if d in ratio_by_date and regime_at(i)==reg:
            fr=fwd_ret(i,20)
            if fr is not None: xs.append(ratio_by_date[d]); ys.append(fr)
    if len(xs)>20:
        print(f"  {reg}: n={len(xs)} Pearson={pearson(xs,ys):+.3f}")

print("\n=== 裁决 ===")
print("Pearson |r|<0.1 且分组无一致方向 → C级噪音 (同外资买超#10)")
print("|r|>0.15 且分组单调 → 有信号苗头, 值得深挖")
