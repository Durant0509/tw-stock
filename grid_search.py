#!/usr/bin/env python3
"""
Entry/Exit 門檻 Grid Search
掃 entry ∈ [8,9,10,11]  ×  exit ∈ [4,5,6,7]  = 16 組合
排序依據：超額年化報酬（策略年化 - 0050年化）
"""
import sys
sys.path.insert(0, '.')

print("載入 scan_backtest 資料...")
import scan_backtest  # 觸發所有資料預載
from scan_backtest import run_backtest

ENTRY_GRID = [8, 9, 10, 11]
EXIT_GRID  = [4, 5, 6, 7]

results = []
total = len(ENTRY_GRID) * len(EXIT_GRID)
done  = 0

print(f"\n開始 Grid Search: {total} 組合\n")

for entry in ENTRY_GRID:
    for exit_ in EXIT_GRID:
        if exit_ >= entry:
            done += 1
            print(f"  [{done:2d}/{total}] entry={entry} exit={exit_}  跳過（exit>=entry）")
            continue
        done += 1
        print(f"  [{done:2d}/{total}] entry={entry} exit={exit_}  跑中...", end='', flush=True)
        r = run_backtest(entry_score=entry, exit_score=exit_, verbose=False)
        s = r['summary']
        results.append({
            'entry': entry, 'exit': exit_,
            'trades':    s['total_trades'],
            'win_rate':  s['win_rate'],
            'avg_win':   s['avg_win'],
            'avg_loss':  s['avg_loss'],
            'ann_ret':   s['ann_ret'],
            'bm_ann':    s['bm_ann_ret'],
            'excess':    s['excess_ann'],
            'mdd':       s['strategy_mdd'],
            'final_eq':  s['final_equity'],
            'invested':  s['total_invested'],
            'sharpe':    s['sharpe_excess_per_mdd'],
        })
        print(f"  超額={s['excess_ann']:+.1f}%  勝率={s['win_rate']:.0f}%  MDD={s['strategy_mdd']:.1f}%  筆數={s['total_trades']}")

# 排序：超額年化 desc
results.sort(key=lambda x: -x['excess'])

print()
print("=" * 90)
print(f"  {'entry':>5} {'exit':>5} {'筆數':>5} {'勝率':>7} {'平均獲利':>9} {'平均虧損':>9} "
      f"{'年化':>7} {'超額':>7} {'MDD':>7} {'最終資產':>10}")
print("=" * 90)
for r in results:
    marker = " ★" if r == results[0] else ""
    print(f"  {r['entry']:>5} {r['exit']:>5} {r['trades']:>5} {r['win_rate']:>6.1f}% "
          f"{r['avg_win']:>+8.2f}% {r['avg_loss']:>+8.2f}% "
          f"{r['ann_ret']:>+6.1f}% {r['excess']:>+6.1f}% {r['mdd']:>6.1f}%  "
          f"{r['final_eq']/10000:>8.1f}萬{marker}")
print("=" * 90)
print()

best = results[0]
print(f"最佳組合: entry={best['entry']} exit={best['exit']}")
print(f"  超額年化 {best['excess']:+.1f}%  年化 {best['ann_ret']:+.1f}%  MDD {best['mdd']:.1f}%")
print(f"  勝率 {best['win_rate']:.1f}%  平均獲利 {best['avg_win']:+.2f}%  平均虧損 {best['avg_loss']:+.2f}%")
print(f"  最終資產 {best['final_eq']/10000:.1f}萬  累計投入 {best['invested']/10000:.1f}萬")
