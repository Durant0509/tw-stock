#!/usr/bin/env python3
"""波浪理論量化驗證 (艾略特五波客觀化)。
用 ZigZag 把價格轉成客觀波段序列 (去主觀數法), 測兩個可交易命題:
  命題A: 斐波那契回撤 (0.382-0.618) 後趨勢波展開 → 進場報酬 vs 隨機基線
  命題B: 「第3波不是最短」規則在真實資料的成立率
裁決: 進場後報酬顯著勝隨機基線 → 有預測力; 否則 C 級噪音。
"""
import statistics as st
import backtest as B
days=B.days

def zigzag(prices, pct=0.05):
    """ZigZag: 只保留 >pct 的轉折。回傳 [(idx, price, type)] type=H/L
    標準實作: 先定初始方向, 再交替確認高低點。"""
    if len(prices)<2: return []
    piv=[]
    ext_i=0; ext_p=prices[0]; trend=None      # trend: 'up'/'down'
    for i in range(1,len(prices)):
        p=prices[i]
        if trend is None:                       # 初始: 等第一次 ±pct 定方向
            if p>=ext_p*(1+pct): trend='up'; piv.append((ext_i,ext_p,'L')); ext_i,ext_p=i,p
            elif p<=ext_p*(1-pct): trend='down'; piv.append((ext_i,ext_p,'H')); ext_i,ext_p=i,p
            elif p>ext_p: ext_i,ext_p=i,p        # 還沒定向, 追蹤極值
            elif p<ext_p: ext_i,ext_p=i,p
        elif trend=='up':
            if p>ext_p: ext_i,ext_p=i,p          # 續創高
            elif p<=ext_p*(1-pct):               # 回落確認高點
                piv.append((ext_i,ext_p,'H')); trend='down'; ext_i,ext_p=i,p
        else:  # down
            if p<ext_p: ext_i,ext_p=i,p          # 續創低
            elif p>=ext_p*(1+pct):               # 反彈確認低點
                piv.append((ext_i,ext_p,'L')); trend='up'; ext_i,ext_p=i,p
    piv.append((ext_i,ext_p,'H' if trend=='up' else 'L'))   # 收尾最後極值
    return piv

def analyze_symbol(code, fwd=20):
    """回傳 (斐波那契回撤進場的報酬清單, 全體隨機基線報酬清單)。
    用 adj_ret 重建分割調整後價格 (T6 鐵則: 避免 2025-06 0050 1:4 分割污染)"""
    px=[100.0]   # 分割調整後合成價格序列
    for i in range(1,len(days)):
        r=B.adj_ret(code,days[i-1],days[i])
        px.append(px[-1]*(1+r))
    piv=zigzag(px, 0.05)
    fib_rets=[]; wave3_ok=0; wave3_tot=0
    # 掃描連續波段: L-H-L (第1波上 + 第2波回) 找斐波那契回撤
    for k in range(len(piv)-2):
        (i0,p0,t0),(i1,p1,t1),(i2,p2,t2)=piv[k],piv[k+1],piv[k+2]
        if t0=='L' and t1=='H' and t2=='L':      # 上升1波 + 回撤2波
            w1=p1-p0
            if w1<=0: continue
            retr=(p1-p2)/w1                        # 第2波回撤比例
            if 0.382<=retr<=0.618:                # 斐波那契黃金回撤區
                # 進場 = 回撤確認點(i2), 看 fwd 日後報酬
                if i2+fwd<len(px) and px[i2]>0:
                    fib_rets.append(px[i2+fwd]/px[i2]-1)
            # 命題B: 5波序列檢查第3波是否最短 (需 L-H-L-H-L-H)
        if k<len(piv)-5:
            seq=piv[k:k+6]
            if [x[2] for x in seq]==['L','H','L','H','L','H']:
                w1=seq[1][1]-seq[0][1]; w3=seq[3][1]-seq[2][1]; w5=seq[5][1]-seq[4][1]
                if w1>0 and w3>0 and w5>0:
                    wave3_tot+=1
                    if w3>=w1 and w3>=w5: wave3_ok+=1   # 第3波最長(不是最短)
    # 隨機基線: 全期任意日 fwd 報酬
    base=[]
    for i in range(0,len(px)-fwd,5):
        if px[i]>0: base.append(px[i+fwd]/px[i]-1)
    return fib_rets, base, wave3_ok, wave3_tot

SYMBOLS=['0050','2330','2454','2317','2308','3037','2603','2882']
print("=== 波浪理論量化驗證 ===\n")
all_fib=[]; all_base=[]; w3_ok=0; w3_tot=0
print(f"{'標的':<8}{'斐波那契進場n':>12}{'進場avg':>10}{'隨機基線avg':>12}{'第3波最長率':>12}")
for code in SYMBOLS:
    fib,base,wok,wtot=analyze_symbol(code)
    all_fib+=fib; all_base+=base; w3_ok+=wok; w3_tot+=wtot
    fa=st.mean(fib)*100 if fib else 0
    ba=st.mean(base)*100 if base else 0
    w3=f"{wok}/{wtot}" if wtot else "n/a"
    print(f"{code:<8}{len(fib):>12}{fa:>9.2f}%{ba:>11.2f}%{w3:>12}")

print(f"\n=== 彙總裁決 ===")
fib_avg=st.mean(all_fib)*100 if all_fib else 0
base_avg=st.mean(all_base)*100 if all_base else 0
fib_win=100*sum(1 for r in all_fib if r>0)/len(all_fib) if all_fib else 0
base_win=100*sum(1 for r in all_base if r>0)/len(all_base) if all_base else 0
print(f"命題A 斐波那契回撤進場: n={len(all_fib)}, avg {fib_avg:+.2f}% (勝率 {fib_win:.0f}%)")
print(f"       隨機基線:         n={len(all_base)}, avg {base_avg:+.2f}% (勝率 {base_win:.0f}%)")
edge=fib_avg-base_avg
print(f"       → edge vs 基線: {edge:+.2f}pp")
print(f"命題B 第3波不是最短: {w3_ok}/{w3_tot} = {100*w3_ok/w3_tot:.0f}% (隨機期望~33%)" if w3_tot else "命題B n/a")
print(f"\n裁決:")
if edge>1.0 and fib_avg>0: print("  🟢 斐波那契回撤有預測力 (勝隨機基線 >1pp), 值得深挖")
elif abs(edge)<=1.0: print("  🔴 斐波那契回撤 ≈ 隨機基線, 無 alpha (C級, 同外資買超命運)")
else: print("  🔴 斐波那契回撤反而輸基線")
