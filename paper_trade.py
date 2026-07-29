#!/usr/bin/env python3
"""
模擬盤管理器
每日由 update.py 呼叫。讀取 scan_data.json 決定進出場，
狀態存在 paper_trade.json（git 追蹤，每日快照）。

進場規則：
  - regime != 'bear'（bear 閘門）
  - scan_score >= 10
  - 無上限（歷史統計通常每天 1~2 支）

出場規則：
  - scan_score <= 6
  - 持有 >= 60 個交易日
  - 收盤跌破 MA60 * 0.98
  - 外資連賣 >= 5 日
  - 從進場日收盤 跌幅 >= -10%（停損）
"""
import json, os
from datetime import datetime

PAPER_FILE = 'paper_trade.json'
ENTRY_SCORE = 10
EXIT_SCORE  = 6
MAX_POS     = 99  # 無上限，好的訊號全進
MAX_HOLD    = 60   # 交易日
STOP_LOSS   = -0.10

def load_state():
    if os.path.exists(PAPER_FILE):
        return json.load(open(PAPER_FILE, encoding='utf-8'))
    return {'positions': {}, 'closed': [], 'log': [], 'start_date': None}

def save_state(state):
    json.dump(state, open(PAPER_FILE, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

def run():
    # 讀今日掃描結果
    if not os.path.exists('scan_data.json'):
        print("paper_trade: scan_data.json 不存在，跳過")
        return
    scan = json.load(open('scan_data.json', encoding='utf-8'))
    today = scan['asof'].replace('-','')  # '20260729'
    regime = scan['regime']
    gate   = scan['gate']
    all_stocks = {s['code']: s for s in scan.get('top', []) + scan.get('watch', [])}
    score_map = {s['code']: s['pts'] for s in all_stocks.values()}

    state = load_state()
    if not state['start_date']:
        state['start_date'] = today

    log_entries = []

    # ── 出場檢查 ──────────────────────────────────────────────────────────
    to_exit = []
    for code, pos in list(state['positions'].items()):
        s = all_stocks.get(code)
        cur_px = s['close'] if s else pos['entry_px']
        score  = score_map.get(code)
        gross_ret = (cur_px - pos['entry_px']) / pos['entry_px']
        hold_days = pos.get('hold_days', 0) + 1

        # 更新今日收盤
        state['positions'][code]['cur_px']    = cur_px
        state['positions'][code]['hold_days'] = hold_days
        state['positions'][code]['gross_ret'] = round(gross_ret*100, 2)

        # 出場條件
        reason = None
        if gross_ret <= STOP_LOSS:
            reason = f'停損 ({gross_ret*100:+.1f}%)'
        elif score is not None and score <= EXIT_SCORE:
            reason = f'分數降至 {score}'
        elif hold_days >= MAX_HOLD:
            reason = f'持有 {hold_days} 日到期'
        elif s:
            ma60_pct = s.get('above_ma60', 0) or 0
            if ma60_pct < -2:
                reason = f'破MA60 ({ma60_pct:+.1f}%)'
            fs = s.get('fstreak', 0) or 0
            if fs <= -5:
                reason = f'外資連賣 {abs(fs)} 日'

        if reason:
            to_exit.append((code, reason, cur_px, gross_ret, hold_days))

    for code, reason, cur_px, gross_ret, hold_days in to_exit:
        pos = state['positions'].pop(code)
        net_ret = gross_ret - 0.001425 - 0.003 - 0.001  # 買+賣成本
        record = {
            'code': code, 'name': pos.get('name',''),
            'entry_date': pos['entry_date'], 'exit_date': today,
            'entry_px': pos['entry_px'], 'exit_px': cur_px,
            'gross_ret': round(gross_ret*100, 2),
            'net_ret': round(net_ret*100, 2),
            'hold_days': hold_days, 'reason': reason,
            'entry_score': pos.get('entry_score')
        }
        state['closed'].append(record)
        log_entries.append(f"[出場] {code} {pos.get('name','')} {reason}  net={net_ret*100:+.1f}%")

    # ── 進場掃描 ──────────────────────────────────────────────────────────
    # bear 閘門：bear 時不進新倉
    if regime == 'bear':
        log_entries.append(f"[閘門] bear regime，不開新倉")
    else:
        # 所有達到門檻的股票都進，不限數量
        candidates = sorted(
            [(s['pts'], s['code'], s) for s in all_stocks.values()
             if s['code'] not in state['positions'] and s['pts'] >= ENTRY_SCORE],
            reverse=True
        )
        for _, _code, s in candidates:
            code = s['code']
            entry_px = s['close']
            state['positions'][code] = {
                'code': code, 'name': s['name'],
                'entry_date': today, 'entry_px': entry_px,
                'entry_score': s['pts'],
                'cur_px': entry_px, 'hold_days': 0,
                'gross_ret': 0.0,
                'reasons': s.get('reasons', []),
                'flags': s.get('flags', [])
            }
            log_entries.append(
                f"[進場] {code} {s['name']}  分={s['pts']}  "
                f"MA60={s.get('above_ma60',0):+.1f}%  "
                f"外資={s.get('fstreak',0):+d}日"
            )

    # ── 統計 ─────────────────────────────────────────────────────────────
    closed = state['closed']
    n = len(closed)
    wins = [r for r in closed if r['net_ret'] > 0]
    total_net = sum(r['net_ret'] for r in closed) / 100
    win_rate = len(wins)/n*100 if n else 0
    avg_win  = sum(r['net_ret'] for r in wins)/len(wins) if wins else 0
    losses_l = [r for r in closed if r['net_ret'] <= 0]
    avg_loss = sum(r['net_ret'] for r in losses_l)/len(losses_l) if losses_l else 0

    state['summary'] = {
        'asof': today,
        'regime': regime, 'gate': gate,
        'open_positions': len(state['positions']),
        'closed_trades': n,
        'win_rate': round(win_rate, 1),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'pnl_ratio': round(abs(avg_win/avg_loss), 2) if avg_loss else None,
        'total_net_pct': round(total_net*100, 2),
    }

    if log_entries:
        state['log'].append({'date': today, 'events': log_entries})

    save_state(state)
    print(f"模擬盤更新: {today}  持倉={len(state['positions'])}  已結={n}  "
          f"勝率={win_rate:.0f}%  今日事件={len(log_entries)}")
    for e in log_entries:
        print(f"  {e}")

if __name__ == '__main__':
    run()
