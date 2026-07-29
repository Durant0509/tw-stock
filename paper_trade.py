#!/usr/bin/env python3
"""
模擬盤管理器
每日由 update.py 呼叫。讀取 scan_data.json 決定進出場，
狀態存在 paper_trade.json（git 追蹤，每日快照）。

資金模式：固定 LOT_SIZE = 100,000 元/支
- 現金不夠時自動「追加注資」並記錄，帳戶成本因此上升
- 出場後現金回收，等下一筆進場

進場規則：
  - regime != 'bear'
  - scan_score >= 10

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
MAX_HOLD    = 60        # 交易日
STOP_LOSS   = -0.10
LOT_SIZE    = 100_000   # 每支固定 10 萬元

BUY_COST  = 0.001425 + 0.0005   # 買進摩擦
SELL_COST = 0.001425 + 0.003 + 0.0005  # 賣出摩擦（含證交稅）

def load_state():
    if os.path.exists(PAPER_FILE):
        return json.load(open(PAPER_FILE, encoding='utf-8'))
    return {
        'positions': {}, 'closed': [], 'log': [],
        'start_date': None,
        'cash': LOT_SIZE,          # 初始現金 = 1 lot，首筆進場剛好夠
        'total_invested': LOT_SIZE, # 累計注入成本
        'equity_curve': [],
    }

def save_state(state):
    json.dump(state, open(PAPER_FILE, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

def run():
    if not os.path.exists('scan_data.json'):
        print("paper_trade: scan_data.json 不存在，跳過")
        return
    scan = json.load(open('scan_data.json', encoding='utf-8'))
    today  = scan['asof'].replace('-', '')
    regime = scan['regime']
    all_stocks = {s['code']: s for s in scan.get('top', []) + scan.get('watch', [])}
    score_map  = {s['code']: s['pts'] for s in all_stocks.values()}

    state = load_state()
    if not state['start_date']:
        state['start_date'] = today
    # 相容舊格式：有 capital 欄位的舊版本
    if 'cash' not in state:
        cap = state.get('capital', LOT_SIZE)
        state['cash'] = cap
        state['total_invested'] = cap
    if 'equity_curve' not in state:
        state['equity_curve'] = []

    log_entries = []

    # ── 出場 ────────────────────────────────────────────────────────────────
    to_exit = []
    for code, pos in list(state['positions'].items()):
        s       = all_stocks.get(code)
        cur_px  = s['close'] if s else pos['entry_px']
        score   = score_map.get(code)
        gross   = (cur_px - pos['entry_px']) / pos['entry_px']
        hold    = pos.get('hold_days', 0) + 1

        ma60_pct = (s.get('above_ma60', 0) or 0) if s else 0
        fs       = (s.get('fstreak', 0) or 0) if s else 0
        stop_dist = round((gross - STOP_LOSS) * 100, 2)   # 距止損還剩幾 %（正=安全）

        state['positions'][code].update({
            'cur_px':    cur_px,
            'hold_days': hold,
            'gross_ret': round(gross * 100, 2),
            # 出場信號狀態（每日更新，網頁顯示用）
            'score':     score,
            'ma60_pct':  round(ma60_pct, 1),
            'fstreak':   fs,
            'stop_dist': stop_dist,   # 正值=離停損還有多遠，負=已超
        })

        reason = None
        if gross <= STOP_LOSS:
            reason = f'停損 ({gross*100:+.1f}%)'
        elif score is not None and score <= EXIT_SCORE:
            reason = f'分數降至 {score}'
        elif hold >= MAX_HOLD:
            reason = f'持有 {hold} 日到期'
        elif s:
            if ma60_pct < -2:
                reason = f'破MA60 ({ma60_pct:+.1f}%)'
            if not reason and fs <= -5:
                reason = f'外資連賣 {abs(fs)} 日'

        if reason:
            to_exit.append((code, reason, cur_px, gross, hold))

    for code, reason, cur_px, gross, hold in to_exit:
        pos    = state['positions'].pop(code)
        net    = gross - BUY_COST - SELL_COST
        lot    = pos.get('lot', LOT_SIZE)
        net_tw = round(lot * net)
        # 出場後現金回收
        state['cash'] = round(state['cash'] + lot + net_tw)
        record = {
            'code': code, 'name': pos.get('name', ''),
            'entry_date': pos['entry_date'], 'exit_date': today,
            'entry_px': pos['entry_px'], 'exit_px': cur_px,
            'gross_ret': round(gross * 100, 2),
            'net_ret':   round(net * 100, 2),
            'lot': lot, 'net_twd': net_tw,
            'hold_days': hold, 'reason': reason,
            'entry_score': pos.get('entry_score'),
        }
        state['closed'].append(record)
        sign = '+' if net_tw >= 0 else ''
        log_entries.append(
            f"[出場] {code} {pos.get('name','')} {reason}  "
            f"net={net*100:+.1f}%  ({sign}{net_tw:,} 元)  現金={state['cash']:,}"
        )

    # ── 進場 ────────────────────────────────────────────────────────────────
    if regime == 'bear':
        log_entries.append("[閘門] bear regime，不開新倉")
    else:
        candidates = sorted(
            [(s['pts'], s['code'], s) for s in all_stocks.values()
             if s['code'] not in state['positions'] and s['pts'] >= ENTRY_SCORE],
            reverse=True
        )
        for _, _code, s in candidates:
            code = s['code']
            # 現金不夠 → 追加注資
            if state['cash'] < LOT_SIZE:
                add = LOT_SIZE - state['cash']
                state['cash'] += add
                state['total_invested'] += add
                log_entries.append(f"[注資] +{add:,} 元 → 累計投入 {state['total_invested']:,}")
            # 買進
            state['cash'] -= LOT_SIZE
            state['positions'][code] = {
                'code': code, 'name': s['name'],
                'entry_date': today, 'entry_px': s['close'],
                'entry_score': s['pts'],
                'cur_px': s['close'], 'hold_days': 0,
                'gross_ret': 0.0,
                'lot': LOT_SIZE,
                'reasons': s.get('reasons', []),
                'flags':   s.get('flags', []),
            }
            log_entries.append(
                f"[進場] {code} {s['name']}  分={s['pts']}  "
                f"MA60={s.get('above_ma60',0):+.1f}%  "
                f"外資={s.get('fstreak',0):+d}日  "
                f"配置={LOT_SIZE:,}元  現金剩={state['cash']:,}"
            )

    # ── 每日淨值 ─────────────────────────────────────────────────────────────
    open_unreal = sum(
        round(pos['lot'] * (pos['gross_ret'] / 100) - pos['lot'] * BUY_COST)
        for pos in state['positions'].values()
    )
    realized = sum(r.get('net_twd', 0) for r in state['closed'])
    # 帳戶市值 = 現金 + 所有持倉現值（以 lot 為基準）
    pos_market_val = sum(
        round(pos['lot'] * (1 + pos['gross_ret'] / 100))
        for pos in state['positions'].values()
    )
    total_equity = state['cash'] + pos_market_val
    total_ret_pct = round((total_equity / state['total_invested'] - 1) * 100, 2)

    state['equity_curve'].append({
        'date': today,
        'cash': state['cash'],
        'equity': total_equity,
        'invested': state['total_invested'],
        'ret_pct': total_ret_pct,
    })

    # ── 統計 ─────────────────────────────────────────────────────────────────
    closed = state['closed']
    n      = len(closed)
    wins   = [r for r in closed if r['net_ret'] > 0]
    losses = [r for r in closed if r['net_ret'] <= 0]
    win_rate  = len(wins) / n * 100 if n else 0
    avg_win   = sum(r['net_ret'] for r in wins)   / len(wins)   if wins   else 0
    avg_loss  = sum(r['net_ret'] for r in losses) / len(losses) if losses else 0
    total_net = sum(r.get('net_twd', 0) for r in closed)

    state['summary'] = {
        'asof': today, 'regime': regime,
        'lot_size': LOT_SIZE,
        'total_invested': state['total_invested'],
        'cash': state['cash'],
        'open_positions': len(state['positions']),
        'pos_market_val': pos_market_val,
        'total_equity': total_equity,
        'total_ret_pct': total_ret_pct,
        'closed_trades': n,
        'win_rate': round(win_rate, 1),
        'avg_win':  round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'pnl_ratio': round(abs(avg_win / avg_loss), 2) if avg_loss else None,
        'realized_net_twd': total_net,
        'open_unreal_twd':  open_unreal,
    }

    if log_entries:
        state['log'].append({'date': today, 'events': log_entries})

    save_state(state)
    print(f"模擬盤更新: {today}  持倉={len(state['positions'])}  已結={n}  "
          f"勝率={win_rate:.0f}%  投入={state['total_invested']:,}  "
          f"資產={total_equity:,} ({total_ret_pct:+.2f}%)")
    for e in log_entries:
        print(f"  {e}")

if __name__ == '__main__':
    run()
