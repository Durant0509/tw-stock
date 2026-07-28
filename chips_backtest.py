#!/usr/bin/env python3
"""法人筹码因子预测力验证 → chips_backtest_data.json。
铁律(见 memory/factor-research-findings + backtest-methodology-discipline):
- 用 IC(信息系数) + 分位数未来报酬, 验证每个筹码因子对未来 5/20 日 0050 报酬的预测力
- 诚实呈现: 无预测力就标 weak, 不硬凑
- 只有验证有效(|IC|够大且方向合理)的因子, 阶段4才写进大盘建议

因子(能在现有资料上算的):
  1. 外资台指期净未平仓「水位」(z-score) → 反指? 顺势?
  2. 外资台指期净未平仓「日增减」→ 动能?
  (MTX散户/TXO选择权/现货金额 待 Windows 全量回补后纳入; 此处先跑外资期货)
"""
import json, glob, math
import statistics as st
from collections import defaultdict
import backtest as B
days=B.days
d2i={d:i for i,d in enumerate(days)}
fmt=lambda d:f"{d[:4]}-{d[4:6]}-{d[6:]}"   # YYYYMMDD -> YYYY-MM-DD

# 0050 未来 N 日报酬 + regime
adj=[100.0]
for i in range(1,len(days)): adj.append(adj[-1]*(1+B.adj_ret('0050',days[i-1],days[i])))
def fwd_ret(i,n):
    if i+n>=len(adj): return None
    return adj[i+n]/adj[i]-1
def ma_(i,w=60): seg=adj[max(0,i-w+1):i+1]; return sum(seg)/len(seg)
def regime_i(i):
    if i<80: return 'warmup'
    s=ma_(i)/ma_(i-20)-1
    return 'bull' if s>0.02 else 'bear' if s<-0.02 else 'range'

# --- 载入外资台指期净未平仓 (from finmind) ---
def load_tx_foreign():
    by=defaultdict(int)
    for fp in sorted(glob.glob('data/finmind/inst_*.json')):
        try: rows=json.load(open(fp,encoding='utf-8'))
        except: continue
        for r in rows:
            if r.get('institutional_investors')=='外資':
                by[r['date']]+=r['long_open_interest_balance_volume']-r['short_open_interest_balance_volume']
    # 对齐交易日 index
    out={}
    for d,v in by.items():
        ds=d.replace('-','')
        if ds in d2i: out[d2i[ds]]=v
    return out

# --- 载入现货投信买超金额 (from chips spot BFI82U) → 研究证实反指 ---
def load_spot_trust():
    import os
    out={}
    for fp in sorted(glob.glob('data/chips/spot_*.json')):
        ds=os.path.basename(fp)[5:-5]
        if ds not in d2i: continue
        try: d=json.load(open(fp,encoding='utf-8'))
        except: continue
        for row in d.get('data',[]):
            if row and row[0]=='投信':
                try: out[d2i[ds]]=float(str(row[-1]).replace(',',''))/1e8
                except: pass
    return out

def spearman_ic(pairs):
    """pairs=[(factor, fwd_ret)]; 回 Spearman 秩相关 (IC)。"""
    pairs=[(x,y) for x,y in pairs if x is not None and y is not None]
    if len(pairs)<30: return None,0
    def rank(vals):
        order=sorted(range(len(vals)),key=lambda i:vals[i])
        rk=[0]*len(vals)
        for r,i in enumerate(order): rk[i]=r
        return rk
    xs=[p[0] for p in pairs]; ys=[p[1] for p in pairs]
    rx,ry=rank(xs),rank(ys); n=len(xs)
    mx=st.mean(rx); my=st.mean(ry)
    num=sum((rx[i]-mx)*(ry[i]-my) for i in range(n))
    den=math.sqrt(sum((rx[i]-mx)**2 for i in range(n))*sum((ry[i]-my)**2 for i in range(n)))
    return (num/den if den else 0), n

def quantile_fwd(pairs, nq=5):
    """把因子分 nq 组, 回每组平均未来报酬 (%). 看单调性。"""
    pairs=[(x,y) for x,y in pairs if x is not None and y is not None]
    if len(pairs)<nq*10: return None
    pairs.sort()
    per=len(pairs)//nq; out=[]
    for q in range(nq):
        seg=pairs[q*per:(q+1)*per] if q<nq-1 else pairs[q*per:]
        out.append(round(100*st.mean([p[1] for p in seg]),2))
    return out

def verdict(ic, n):
    """IC 绝对值裁决 (股票日频 IC>0.05 已算有讯号, >0.1 强)。"""
    if ic is None: return 'insufficient'
    a=abs(ic)
    if a>=0.10: return 'strong'
    if a>=0.05: return 'moderate'
    if a>=0.03: return 'weak'
    return 'none'

tx=load_tx_foreign()
spot_trust=load_spot_trust()
idxs=sorted(tx)

# 通用: 60日 z-score 水位 (去长期趋势)
def zscore_of(series):
    ii=sorted(series); vals=[series[i] for i in ii]; out={}
    for k,i in enumerate(ii):
        if k<60: continue
        window=vals[k-60:k]
        m=st.mean(window); sd=st.pstdev(window)
        out[i]=(series[i]-m)/sd if sd>0 else 0
    return out

# 因子1: 外资期货净未平仓「水位」(顺势, 研究IC 0.15)
def zscore_series(): return zscore_of(tx)
# 因子2: 外资期货净未平仓「日增减」
def chg_series():
    out={}
    for k in range(1,len(idxs)):
        i=idxs[k]; ip=idxs[k-1]
        if i-ip<=3: out[i]=tx[i]-tx[ip]
    return out

results=[]
for name,desc,ser,hypo in [
    ('tx_foreign_level','外资台指期净未平仓水位(60日z-score)',zscore_series(),'水位极端→反转? 或顺势?'),
    ('tx_foreign_chg','外资台指期净未平仓日增减',chg_series(),'外资加空→未来偏空(顺势)?'),
    ('spot_trust_level','现货投信买超水位(60日z-score)',zscore_of(spot_trust),'投信大买→反指(未来偏弱)?'),
]:
    row={'factor':name,'desc':desc,'hypo':hypo,'horizons':{}}
    for n in (5,20):
        pairs=[(ser[i], fwd_ret(i,n)) for i in ser]
        ic,cnt=spearman_ic(pairs)
        q=quantile_fwd(pairs,5)
        row['horizons'][f'{n}d']={
            'ic':round(ic,4) if ic is not None else None,
            'n':cnt,'verdict':verdict(ic,cnt),
            'quantile_fwd':q   # 5组由低到高因子, 各组平均未来报酬%
        }
    # 分市况 IC (未来20日) — 验证是否单一波段假象 (memory R22 纪律)
    regic={}
    for rg in ('bull','bear','range'):
        pairs=[(ser[i], fwd_ret(i,20)) for i in ser if regime_i(i)==rg]
        ic,cnt=spearman_ic(pairs)
        regic[rg]={'ic':round(ic,4) if ic is not None else None,'n':cnt}
    row['regime_ic']=regic
    # 综合裁决: 20日IC + 三市况方向是否一致 (跨市况稳定才算真讯号)
    ic20=row['horizons']['20d']['ic']
    regvals=[regic[rg]['ic'] for rg in ('bull','bear','range') if regic[rg]['ic'] is not None]
    consistent=len(regvals)>=2 and (all(v>0 for v in regvals) or all(v<0 for v in regvals))
    row['stable']=bool(ic20 and abs(ic20)>=0.05 and consistent)
    row['direction']='顺势' if (ic20 or 0)>0 else '反向'
    results.append(row)

out={'asof':fmt(days[-1]),
     'note':'IC=Spearman秩相关(因子 vs 未来N日0050报酬). |IC|>=0.05有讯号, >=0.1强. quantile_fwd=因子五分位各组未来报酬%(看单调性).',
     'factors':results,
     'coverage':'目前仅外资台指期(finmind历史980天). MTX散户/TXO选择权/现货金额待Windows全量回补后纳入.'}
json.dump(out,open('chips_backtest_data.json','w',encoding='utf-8'),ensure_ascii=False)

print("=== 法人筹码因子预测力验证 ===\n")
for r in results:
    print(f"因子: {r['desc']}")
    for n in ('5d','20d'):
        h=r['horizons'][n]
        vmap={'strong':'🟢强','moderate':'🟡中','weak':'🟠弱','none':'🔴无','insufficient':'⚫资料不足'}
        print(f"  未来{n}: IC={h['ic']} (n={h['n']}) → {vmap.get(h['verdict'],h['verdict'])}")
        if h['quantile_fwd']: print(f"         五分位未来报酬%: {h['quantile_fwd']} (低因子→高因子)")
    ri=r['regime_ic']
    print(f"  分市况IC20: 牛{ri['bull']['ic']} 熊{ri['bear']['ic']} 盘{ri['range']['ic']}")
    print(f"  → 裁决: {'✅ 跨市况稳定, 可纳入建议' if r['stable'] else '⚠️ 不够稳定, 仅供参考'} ({r['direction']})")
    print()
print("chips_backtest_data.json 输出完成")
