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

PAPER_FILE  = 'paper_trade.json'
ENTRY_SCORE = 10
EXIT_SCORE  = 6
MAX_POS     = 99   # 無上限，好的訊號全進
MAX_HOLD    = 60   # 交易日
STOP_LOSS   = -0.10
CAPITAL     = 500_000  # 模擬本金（TWD）

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
    if 'capital' not in state:
        state['capital'] = CAPITAL
    if 'equity_curve' not in state:
        state['equity_curve'] = []

    log_entries = []

    # ── 每日持倉更新 + 出場檢查 ──────────────────────────────────────────
    n_pos = len(state['positions'])  # 今日開始時的持倉數（計算等權比重用）
    to_exit = []
    for code, pos in list(state['positions'].items()):
        s = all_stocks.get(code)
        cur_px = s['close'] if s else pos['entry_px']
        score  = score_map.get(code)
        gross_ret = (cur_px - pos['entry_px']) / pos['entry_px']
        hold_days = pos.get('hold_days', 0) + 1

        # 等權重：每支佔本金的 1/N，N = 今日持倉數
        weight = 1.0 / n_pos if n_pos > 0 else 0
        allocated = round(CAPITAL * weight)   # 分配到這支的金額
        pnl_twd   = round(allocated * gross_ret)  # 未實現損益（元）

        # 更新今日收盤
        state['positions'][code].update({
            'cur_px':   cur_px,
            'hold_days': hold_days,
            'gross_ret': round(gross_ret*100, 2),
            'weight':    round(weight*100, 1),   # %
            'allocated': allocated,
            'pnl_twd':   pnl_twd,
        })

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
            if not reason and fs <= -5:
                reason = f'外資連賣 {abs(fs)} 日'

        if reason:
            to_exit.append((code, reason, cur_px, gross_ret, hold_days, allocated))

    for code, reason, cur_px, gross_ret, hold_days, allocated in to_exit:
        pos = state['positions'].pop(code)
        net_ret = gross_ret - 0.001425 - 0.003 - 0.001  # 買+賣手續費+證交稅
        net_twd = round(allocated * net_ret)
        record = {
            'code': code, 'name': pos.get('name', ''),
            'entry_date': pos['entry_date'], 'exit_date': today,
            'entry_px': pos['entry_px'], 'exit_px': cur_px,
            'gross_ret': round(gross_ret*100, 2),
            'net_ret':   round(net_ret*100, 2),
            'allocated': allocated,   # 這筆投入金額（元）
            'net_twd':   net_twd,     # 這筆淨損益（元）
            'hold_days': hold_days,
            'reason': reason,
            'entry_score': pos.get('entry_score'),
        }
        state['closed'].append(record)
        sign = '+' if net_twd >= 0 else ''
        log_entries.append(
            f"[出場] {code} {pos.get('name','')} {reason}  "
            f"net={net_ret*100:+.1f}%  ({sign}{net_twd:,} 元)"
        )

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
        new_entries = []
        for _, _code, s in candidates:
            code = s['code']
            state['positions'][code] = {
                'code': code, 'name': s['name'],
                'entry_date': today, 'entry_px': s['close'],
                'entry_score': s['pts'],
                'cur_px': s['close'], 'hold_days': 0,
                'gross_ret': 0.0,
                'weight': 0.0, 'allocated': 0, 'pnl_twd': 0,
                'reasons': s.get('reasons', []),
                'flags':   s.get('flags', []),
            }
            new_entries.append((s['pts'], code, s))
        # 所有進場後統一重算等權比重
        n_new = len(state['positions'])
        if n_new > 0:
            per = round(CAPITAL / n_new)
            for c in state['positions']:
                state['positions'][c]['weight']    = round(100/n_new, 1)
                state['positions'][c]['allocated'] = per
        for pts, code, s in new_entries:
            per = state['positions'][code]['allocated']
            log_entries.append(
                f"[進場] {code} {s['name']}  分={pts}  "
                f"MA60={s.get('above_ma60',0):+.1f}%  "
                f"外資={s.get('fstreak',0):+d}日  "
                f"配置≈{per:,}元"
            )

    # ── 每日淨值（等權重，與回測一致）────────────────────────────────────
    # 持倉中每支的未實現損益加總 / 總本金 = 當日總報酬率
    open_pnl = sum(pos.get('pnl_twd', 0) for pos in state['positions'].values())
    total_equity = CAPITAL + open_pnl + sum(r.get('net_twd', 0) for r in state['closed'])
    total_ret_pct = round((total_equity / CAPITAL - 1) * 100, 2)
    state['equity_curve'].append({'date': today, 'equity': total_equity, 'ret_pct': total_ret_pct})

    # ── 統計 ─────────────────────────────────────────────────────────────
    closed = state['closed']
    n = len(closed)
    wins    = [r for r in closed if r['net_ret'] > 0]
    losses_l = [r for r in closed if r['net_ret'] <= 0]
    win_rate = len(wins)/n*100 if n else 0
    avg_win  = sum(r['net_ret'] for r in wins)/len(wins) if wins else 0
    avg_loss = sum(r['net_ret'] for r in losses_l)/len(losses_l) if losses_l else 0
    total_net_twd = sum(r.get('net_twd', 0) for r in closed)

    state['summary'] = {
        'asof': today,
        'capital': CAPITAL,
        'regime': regime, 'gate': gate,
        'open_positions': len(state['positions']),
        'closed_trades': n,
        'win_rate': round(win_rate, 1),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'pnl_ratio': round(abs(avg_win/avg_loss), 2) if avg_loss else None,
        'total_net_twd': total_net_twd,     # 已實現累計損益（元）
        'open_pnl_twd': open_pnl,           # 未實現損益（元）
        'total_equity': total_equity,        # 當前總資產（元）
        'total_ret_pct': total_ret_pct,      # 總報酬率%
    }

    if log_entries:
        state['log'].append({'date': today, 'events': log_entries})

    save_state(state)
    print(f"模擬盤更新: {today}  持倉={len(state['positions'])}  已結={n}  "
          f"勝率={win_rate:.0f}%  總資產={total_equity:,.0f}元 ({total_ret_pct:+.2f}%)")
    for e in log_entries:
        print(f"  {e}")

if __name__ == '__main__':
    run()
