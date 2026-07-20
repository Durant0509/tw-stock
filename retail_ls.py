#!/usr/bin/env python3
"""复现「真散户多空比」(图的算法) + 验证反向指标。
散户多单 = 全市场多单 - 三法人多单; 散户空单 = 全市场空单 - 三法人空单
散户多空比 = (散户多单 - 散户空单) / 全市场未平仓
命题: 散户极端偏多 → 未来大盘下跌 (反向指标)?
资料: taifex(法人未平仓, 17月) + large(全市场). TXF 大台.
"""
import statistics as st
import backtest as B
days=B.days

def parse_taifex():
    """回传 {date: (法人多单合计, 法人空单合计)}"""
    import glob,os
    out={}
    for fp in sorted(glob.glob('data/taifex/*.csv')):
        raw=open(fp,encoding='big5',errors='ignore').read()
        from collections import defaultdict
        byday=defaultdict(lambda:[0,0])
        for l in raw.split('\n'):
            if not l.strip() or not l[:4].isdigit(): continue
            c=[x.strip().replace(',','') for x in l.split(',')]
            if len(c)>=12:
                try:
                    byday[c[0].replace('/','')][0]+=float(c[9])   # 多方未平仓
                    byday[c[0].replace('/','')][1]+=float(c[11])  # 空方未平仓
                except: pass
        out.update(byday)
    return out

def parse_large_total():
    """回传 {date: 全市场未平仓} 从 large CSV (TX, 所有契约)"""
    import glob,os
    out={}
    for fp in sorted(glob.glob('data/large/*.csv')):
        raw=open(fp,'rb').read().decode('cp950',errors='ignore')
        for l in raw.split('\n'):
            c=l.split(',')
            if len(c)<10 or c[1].strip()!='TX': continue
            if c[3].strip() not in ('666666','999999'): continue
            try:
                date=c[0].strip().replace('/',''); total=float(c[9].strip().replace(',',''))
                if total>0: out[date]=total
            except: pass
    return out

inst=parse_taifex()
total=parse_large_total()
common=sorted(set(inst)&set(total))
print(f"法人未平仓 {len(inst)}天, 全市场 {len(total)}天, 交集 {len(common)}天")
if common: print(f"交集范围: {common[0]} ~ {common[-1]}")

# 散户多空比 = (散户多-散户空)/全市场; 但 large 的全市场是「口数」, taifex 也是口数
# 散户多空净 ≈ -(法人净额) 因为散户是法人对手方; 简化: 散户净 = 全市场无方向, 用 法人多空推
# 图算法: 散户多单=全市场-法人多单... 但全市场未平仓是单边总量
# 实务近似: 散户净部位 = -法人净部位 (期货零和); 散户多空比方向 = -法人净额方向
retail_ls={}
for d in common:
    il,ish=inst[d]; tot=total[d]
    inst_net=il-ish
    # 散户净 = 对手方 ≈ -inst_net; 散户多空比 = 散户净/全市场
    retail_ls[d]=-inst_net/tot if tot>0 else 0

# 0050 fwd 报酬
adj=[100.0]
for i in range(1,len(days)): adj.append(adj[-1]*(1+B.adj_ret('0050',days[i-1],days[i])))
di={d:i for i,d in enumerate(days)}
def fwd(d,f):
    if d not in di: return None
    i=di[d]; return adj[i+f]/adj[i]-1 if i+f<len(adj) else None

# 用交集期间的散户多空比分位, 测极端偏多后报酬
vals=sorted(retail_ls.values())
if len(vals)>20:
    p80=vals[int(len(vals)*0.8)]; p20=vals[int(len(vals)*0.2)]
    print(f"\n散户多空比分布: p20={p20:+.3f} 中位={vals[len(vals)//2]:+.3f} p80={p80:+.3f}")
    for f in [5,10,20]:
        ext_hi=[]; ext_lo=[]; mid=[]
        for d,r in retail_ls.items():
            fr=fwd(d,f)
            if fr is None: continue
            if r>=p80: ext_hi.append(fr)      # 散户极端偏多
            elif r<=p20: ext_lo.append(fr)    # 散户极端偏空
            else: mid.append(fr)
        def m(x): return st.mean(x)*100 if x else 0
        print(f"  fwd{f}日: 散户极端偏多后 {m(ext_hi):+.2f}% (n={len(ext_hi)}) | "
              f"极端偏空后 {m(ext_lo):+.2f}% (n={len(ext_lo)}) | 中间 {m(mid):+.2f}%")

print("\n=== 裁决 ===")
print("反向指标成立 <=> 散户极端偏多后报酬 < 极端偏空后 (且方向明显)")
print("⚠️ caveat: 仅17月交集、TXF大台非微台TMF、散户净=法人对手方近似")
