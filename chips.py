#!/usr/bin/env python3
"""法人筹码快报计算 → chips_data.json (供网页显示)。
读 data/chips/ (现货BFI82U + MTX期货 + TXO选择权) + data/finmind/ (TX台指期)。
所有数字皆盘后事实, 不做预测判断 (预测力由 chips_backtest.py 验证)。
"""
import json, glob, os
from collections import defaultdict

BASE=os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)

def num(s):
    try: return float(str(s).replace(',',''))
    except: return None

# ========== 1) 现货三大法人买卖超 (BFI82U, 单位: 亿元) ==========
def load_spot():
    """回 {date: {'foreign':外资亿, 'trust':投信亿, 'dealer':自营亿, 'total':合计亿}}"""
    out={}
    for fp in sorted(glob.glob('data/chips/spot_*.json')):
        ds=os.path.basename(fp)[5:-5]  # spot_20260728.json -> 20260728
        try: js=json.load(open(fp,encoding='utf-8'))
        except: continue
        foreign=trust=dealer=total=None
        for row in js.get('data',[]):
            if not row: continue
            name=row[0]; net=num(row[-1])  # 买卖差额在最后一栏
            if net is None: continue
            e=net/1e8  # 元 -> 亿
            if name.startswith('外資及陸資'): foreign=e          # 外资(不含外资自营商)
            elif name=='投信': trust=e
            elif name.startswith('自營商'): dealer=(dealer or 0)+e  # 自行+避险两行加总
            elif name=='合計': total=e
        out[ds]={'foreign':foreign,'trust':trust,'dealer':dealer,'total':total}
    return out

# ========== 2) 期货法人净未平仓 (TX台指 from finmind, MTX小台 from chips) ==========
def load_fut_net(inst_glob, want='外資'):
    """回 {date: 净未平仓} for 指定法人 (net = long_OI - short_OI 合计)。"""
    by=defaultdict(lambda:defaultdict(int))
    for fp in sorted(glob.glob(inst_glob)):
        try: rows=json.load(open(fp,encoding='utf-8'))
        except: continue
        for r in rows:
            inv=r.get('institutional_investors')
            net=r.get('long_open_interest_balance_volume',0)-r.get('short_open_interest_balance_volume',0)
            by[r['date']][inv]+=net
    return by

# ========== 3) 选择权外资买权/卖权净未平仓 + P/C Ratio (TXO) ==========
def load_opt():
    """回 {date: {'call_foreign','put_foreign','pc_ratio'}}。
    P/C Ratio 自算(近似) = 全体PUT未平仓 / 全体CALL未平仓。"""
    by=defaultdict(lambda:{'call_foreign':None,'put_foreign':None,'call_oi':0,'put_oi':0})
    for fp in sorted(glob.glob('data/chips/optinst_*.json')):
        try: rows=json.load(open(fp,encoding='utf-8'))
        except: continue
        for r in rows:
            d=r['date']; cp=r.get('call_put'); inv=r.get('institutional_investors')
            longoi=r.get('long_open_interest_balance_volume',0); shortoi=r.get('short_open_interest_balance_volume',0)
            net=longoi-shortoi
            # 全体 OI (三大法人加总 long) 供 P/C 近似
            if cp=='買權': by[d]['call_oi']+=longoi
            elif cp=='賣權': by[d]['put_oi']+=longoi
            if inv=='外資':
                if cp=='買權': by[d]['call_foreign']=net
                elif cp=='賣權': by[d]['put_foreign']=net
    out={}
    for d,v in by.items():
        pc=round(v['put_oi']/v['call_oi']*100,1) if v['call_oi']>0 else None
        out[d]={'call_foreign':v['call_foreign'],'put_foreign':v['put_foreign'],'pc_ratio':pc}
    return out

# ========== 组装 ==========
spot=load_spot()
tx_by=load_fut_net('data/finmind/inst_*.json')      # 台指期 (含外资)
mtx_by=load_fut_net('data/chips/mtxinst_*.json')    # 小台
opt=load_opt()

# 所有有资料的日期 (以期货为主轴, 最全)
all_dates=sorted(set(tx_by)|set(mtx_by)|set(opt)|set(f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in spot))

def fut_series(by, inv='外資'):
    """外资台指期净未平仓时间序列 [(date, net), ...]。"""
    return [(d, by[d][inv]) for d in sorted(by) if inv in by[d]]

tx_foreign=dict(fut_series(tx_by))       # 外资台指净未平仓
retail_mtx={d: -sum(mtx_by[d].values()) for d in mtx_by}  # 散户小台净 = -(三大法人净合计)

def spot_key(d): return d.replace('-','')

# 当前值 (最新一天)
def latest(d_series):
    if not d_series: return None,None
    ds=sorted(d_series); return ds[-1], d_series[ds[-1]]

# 最新日期: 取所有源里最新的交易日 (现货/期货/选择权任一有资料就算)
# 生产环境各源同步更新会自然对齐; 单源落后时以最新为准, 缺资料的字段显 None (诚实)
cur_date = all_dates[-1] if all_dates else None
prev_date = all_dates[-2] if len(all_dates)>=2 else None

def delta(series, cur):
    """增减 = 该源最新有资料日 - 前一个有资料日 (各源自己的节奏, 不依赖全局prev)。"""
    ds=sorted(series)
    if not ds or series.get(cur) is None: return None
    if cur in ds:
        i=ds.index(cur)
        if i>=1: return series[cur]-series[ds[i-1]]
    return None

def last_date(series):
    """该源最新有资料的日期 (YYYY-MM-DD)。"""
    ds=[d for d in sorted(series) if series[d] is not None]
    return ds[-1] if ds else None

cur={'date':cur_date}
# 现货 (spot 用 YYYYMMDD key, 转回 YYYY-MM-DD 找最新)
spot_dates=sorted(spot)  # YYYYMMDD
sk=spot_dates[-1] if spot_dates else None
sp=spot.get(sk,{}) if sk else {}
cur['spot']={'date':f"{sk[:4]}-{sk[4:6]}-{sk[6:]}" if sk else None,
             'foreign':round(sp['foreign'],1) if sp.get('foreign') is not None else None,
             'trust':round(sp['trust'],1) if sp.get('trust') is not None else None,
             'dealer':round(sp['dealer'],1) if sp.get('dealer') is not None else None,
             'total':round(sp['total'],1) if sp.get('total') is not None else None}
# 外资台指期净未平仓 + 增减 (取 TX 自己最新日)
txd=last_date(tx_foreign)
cur['tx_date']=txd
cur['tx_foreign']=tx_foreign.get(txd)
cur['tx_foreign_chg']=delta(tx_foreign,txd)
# 散户小台 (取 MTX 自己最新日)
mxd=last_date(retail_mtx)
cur['mtx_date']=mxd
cur['retail_mtx']=retail_mtx.get(mxd)
cur['retail_mtx_chg']=delta(retail_mtx,mxd)
# 选择权 (取 TXO 自己最新日)
optd=sorted(opt)[-1] if opt else None
o=opt.get(optd,{}) if optd else {}
cur['opt_date']=optd
cur['opt_call_foreign']=o.get('call_foreign')
cur['opt_put_foreign']=o.get('put_foreign')
cur['pc_ratio']=o.get('pc_ratio')

import statistics as _st
def trend_stats(series, win=90):
    """{date:value} → 趋势+异常判断。
    趋势: 过去win天原始值 mean/std/min/max + hist90折线序列。
    异常: 最新一日「变化量」的 z-score (用过去60日变化量分布)。
      持续趋势(如外资一路加空)不算异常; 只有单日剧变才算 → 避免趋势误报。
    level: normal(|z|<1) / mild(≥1) / anomaly(≥2)。
    """
    ds=[d for d in sorted(series) if series[d] is not None]
    if len(ds)<10: return None
    vals=[series[d] for d in ds]
    w=vals[-win:]
    mean=_st.mean(w); std=_st.pstdev(w)
    cur_v=vals[-1]
    # 日变化量 z-score (异常判断核心)
    chg=[vals[i]-vals[i-1] for i in range(1,len(vals))]
    cur_chg=chg[-1] if chg else None
    zchg=None; level='normal'
    if len(chg)>=20:
        cw=chg[-60:] if len(chg)>=60 else chg
        cm=_st.mean(cw); cs=_st.pstdev(cw)
        if cs>0 and cur_chg is not None:
            zchg=(cur_chg-cm)/cs
            a=abs(zchg)
            level='anomaly' if a>=2 else 'mild' if a>=1 else 'normal'
    # 当前值处于均值上方/下方多少 % (相对 std)
    dev_pct=round((cur_v-mean)/abs(mean)*100,1) if mean else None
    return {
      'mean':round(mean),'std':round(std),'min':round(min(w)),'max':round(max(w)),
      'cur':round(cur_v),'cur_chg':round(cur_chg) if cur_chg is not None else None,
      'zchg':round(zchg,2) if zchg is not None else None,'level':level,
      'dev_pct':dev_pct,'n':len(w),
      'hist90':[[d.replace('-',''), round(series[d])] for d in ds[-win:]]
    }

# P/C ratio 序列 (opt 里)
pc_series={d: opt[d]['pc_ratio'] for d in opt if opt[d].get('pc_ratio') is not None}
opt_call_series={d: opt[d]['call_foreign'] for d in opt if opt[d].get('call_foreign') is not None}
opt_put_series={d: opt[d]['put_foreign'] for d in opt if opt[d].get('put_foreign') is not None}
# 现货三大法人各别历史序列 (YYYY-MM-DD)
def spot_ser(key): return {f"{d[:4]}-{d[4:6]}-{d[6:]}": spot[d][key] for d in spot if spot[d].get(key) is not None}
spot_foreign_series=spot_ser('foreign')
spot_trust_series=spot_ser('trust')
spot_dealer_series=spot_ser('dealer')
spot_total_series=spot_ser('total')

# 每指标趋势+异常
trends={
  'tx_foreign':trend_stats(tx_foreign),
  'retail_mtx':trend_stats(retail_mtx),
  'opt_call_foreign':trend_stats(opt_call_series),
  'opt_put_foreign':trend_stats(opt_put_series),
  'pc_ratio':trend_stats(pc_series),
  'spot_foreign':trend_stats(spot_foreign_series),
  'spot_trust':trend_stats(spot_trust_series),
  'spot_dealer':trend_stats(spot_dealer_series),
  'spot_total':trend_stats(spot_total_series),
}

out={
  'asof':cur_date,
  'current':cur,
  'trends':trends,
}
json.dump(out,open('chips_data.json','w',encoding='utf-8'),ensure_ascii=False)
print(f"chips_data.json 输出完成 | asof={cur_date}")
print(f"  现货外资: {cur['spot']['foreign']} 亿 | 外资台指净未平仓: {cur['tx_foreign']} (增减 {cur['tx_foreign_chg']})")
print(f"  散户小台净未平仓: {cur['retail_mtx']} | 外资买权:{cur['opt_call_foreign']} 卖权:{cur['opt_put_foreign']} | P/C:{cur['pc_ratio']}%")
print("\n=== 趋势+异常判定 ===")
lmap={'normal':'🟢正常','mild':'🟡偏离','anomaly':'🔴异常'}
lbl={'tx_foreign':'外资台指期','retail_mtx':'散户小台','opt_call_foreign':'外资买权','opt_put_foreign':'外资卖权','pc_ratio':'P/C Ratio','spot_foreign':'现货外资','spot_trust':'现货投信','spot_dealer':'现货自营','spot_total':'现货合计'}
for k,t in trends.items():
    if t: print(f"  {lbl[k]:8}: 90天均值{t['mean']:>8} 当前{t['cur']:>8} ({t['dev_pct']:+.0f}%) | 今日变化{t['cur_chg']} z={t['zchg']} {lmap[t['level']]} ({t['n']}天)")
    else: print(f"  {lbl[k]:8}: 历史不足(<10天), 待补")
