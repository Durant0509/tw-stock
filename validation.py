#!/usr/bin/env python3
"""進階驗證 (幣圈大師建議):
1. Monte-Carlo 打亂交易順序 → 真實尾部 MDD 分布 → 定槓桿上限
2. Deflated Sharpe Ratio → 校正多重檢驗 (試了 N 個策略後這 Sharpe 還顯著嗎)
"""
import math, random
import statistics as st
import backtest as B

random.seed(42)   # 可重現

def daily_returns(curve):
    vals=[v for _,v in curve]; out=[]
    for i in range(1,len(vals)):
        if vals[i-1]>0: out.append(vals[i]/vals[i-1]-1)
    return out

def mdd_from_rets(rets):
    v=1.0; peak=1.0; mdd=0
    for r in rets:
        v*=(1+r); peak=max(peak,v); mdd=min(mdd,v/peak-1)
    return mdd

def sharpe(rets, ann=252):
    if len(rets)<2: return 0
    m=st.mean(rets); s=st.pstdev(rets)
    return (m/s)*math.sqrt(ann) if s>0 else 0

def skew_kurt(rets):
    n=len(rets); m=st.mean(rets); s=st.pstdev(rets)
    if s==0: return 0,3
    sk=sum(((r-m)/s)**3 for r in rets)/n
    ku=sum(((r-m)/s)**4 for r in rets)/n
    return sk,ku

def norm_cdf(x): return 0.5*(1+math.erf(x/math.sqrt(2)))
def norm_ppf(p):
    # Acklam 近似
    a=[-3.969683028665376e+01,2.209460984245205e+02,-2.759285104469687e+02,1.383577518672690e+02,-3.066479806614716e+01,2.506628277459239e+00]
    b=[-5.447609879822406e+01,1.615858368580409e+02,-1.556989798598866e+02,6.680131188771972e+01,-1.328068155288572e+01]
    c=[-7.784894002430293e-03,-3.223964580411365e-01,-2.400758277161838e+00,-2.549732539343734e+00,4.374664141464968e+00,2.938163982698783e+00]
    d=[7.784695709041462e-03,3.224671290700398e-01,2.445134137142996e+00,3.754408661907416e+00]
    pl=0.02425
    if p<pl:
        q=math.sqrt(-2*math.log(p)); return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p<=1-pl:
        q=p-0.5; r=q*q; return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    q=math.sqrt(-2*math.log(1-p)); return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)

print("跑 撿便宜(5:5) 全期取日報酬...")
curve,trades=B.run(0.5,0.5,"cheap")
rets=daily_returns(curve)
T=len(rets)
sr=sharpe(rets)
hist_mdd=mdd_from_rets(rets)
print(f"樣本: {T} 日 | 交易 {trades} 筆 | 年化 Sharpe {sr:.3f} | 歷史 MDD {hist_mdd*100:.1f}%\n")

# ---- 1. Monte-Carlo 打亂順序 ----
print("=== 1. Monte-Carlo 打亂交易順序 (1000 次) ===")
N_MC=1000
mdds=[]
for _ in range(N_MC):
    sh=rets[:]; random.shuffle(sh); mdds.append(mdd_from_rets(sh))
mdds.sort()
def pct(p): return mdds[int(p*len(mdds))]*100
print(f"  歷史單一路徑 MDD : {hist_mdd*100:6.1f}%")
print(f"  打亂後 MDD 分布:")
print(f"    中位 (p50)     : {pct(0.50):6.1f}%")
print(f"    p95            : {pct(0.05):6.1f}%   (5% 最壞尾部)")
print(f"    p99            : {pct(0.01):6.1f}%   (1% 最壞尾部)")
print(f"    最壞           : {mdds[0]*100:6.1f}%")
ratio=mdds[int(0.01*len(mdds))]/hist_mdd
print(f"  → p99 是歷史 MDD 的 {ratio:.1f}x。實盤槓桿/部位上限應以 p99 而非歷史值抓")

# ---- 2. Deflated Sharpe Ratio ----
print(f"\n=== 2. Deflated Sharpe Ratio (校正多重檢驗) ===")
N_TRIALS=8   # 誠實估: 撿便宜/純估值/純動能/穩健成長/MA60-only/5:5 + 隱含參數選擇
sk,ku=skew_kurt(rets)
sr_daily=sr/math.sqrt(252)   # 轉回每日
# 期望最大 Sharpe (N 次試驗的選擇偏差基準), Bailey-López de Prado
emc=0.5772156649
sr0_daily=(math.sqrt((1-emc)*norm_ppf(1-1/N_TRIALS)+emc*norm_ppf(1-1/(N_TRIALS*math.e))))*0  # placeholder
# 正確式: E[max SR] ≈ sqrt(Var_SR)*[(1-γ)Φ⁻¹(1-1/N)+γΦ⁻¹(1-1/(N·e))]
# Var_SR 估 ≈ (1/T)*(1 - skew·SR + (kurt-1)/4·SR²)  用日 SR
var_sr=(1/T)*(1 - sk*sr_daily + (ku-1)/4*sr_daily**2)
sd_sr=math.sqrt(abs(var_sr))
sr0=sd_sr*((1-emc)*norm_ppf(1-1/N_TRIALS)+emc*norm_ppf(1-1/(N_TRIALS*math.e)))
# DSR
denom=math.sqrt(1 - sk*sr_daily + (ku-1)/4*sr_daily**2)
dsr=norm_cdf(((sr_daily - sr0)*math.sqrt(T-1))/denom)
print(f"  試驗次數 N (估)   : {N_TRIALS}")
print(f"  日 Sharpe         : {sr_daily:.4f} (年化 {sr:.3f})")
print(f"  偏度 skew         : {sk:.3f} | 峰度 kurt: {ku:.3f}")
print(f"  期望最大 Sharpe SR0: {sr0:.4f} (年化 {sr0*math.sqrt(252):.3f}) ← N 次試驗的選擇偏差門檻")
print(f"  Deflated Sharpe (機率真>0): {dsr:.3f}")
if dsr>0.95: print("  ✅ DSR>0.95: 校正多重檢驗後仍顯著")
elif dsr>0.90: print("  🟡 DSR 0.90-0.95: 邊際顯著")
else: print("  🔴 DSR<0.90: 校正後不顯著, 可能是試多了矇到的")
