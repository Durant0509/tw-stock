#!/usr/bin/env python3
"""组合 warroom.html = 模板 + 最新数据。
数据来源: dashboard_data.json + gate_data.json + stocks_data.json + chips_data.json。
update.py 每日重算那几个 JSON 后, 调这个重生成 warroom.html。
注: 旧版误读静态 gatelight_data.json (从不更新), 已改读每日产出的 gate_data.json。
"""
import json, os
BASE=os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)

def ds(t): return t[::5]  # 降采样

dash=json.load(open('dashboard_data.json',encoding='utf-8'))
gate=json.load(open('gate_data.json',encoding='utf-8'))   # 每日更新版 (非静态 gatelight)
stocks=json.load(open('stocks_data.json',encoding='utf-8'))
# chips_data.json / chips_backtest_data.json 可能尚未产出 (分阶段上线); 缺档时给 None
chips=json.load(open('chips_data.json',encoding='utf-8')) if os.path.exists('chips_data.json') else None
chips_bt=json.load(open('chips_backtest_data.json',encoding='utf-8')) if os.path.exists('chips_backtest_data.json') else None
dash_slim={'current':dash['current'],'engine':ds(dash['engine']),'cheap':ds(dash['cheap']),'retail':ds(dash['retail'])}
merged={'dash':dash_slim,'gate':gate,'stocks':stocks,'chips':chips,'chips_bt':chips_bt}
data_js=json.dumps(merged,ensure_ascii=False)

tmpl=open('warroom_template.html',encoding='utf-8').read()
html=tmpl.replace('__DATA__',data_js)
open('warroom.html','w',encoding='utf-8').write(html)
print(f"warroom.html 重生成完成 ({len(html)} bytes, asof {dash['current']['date']})")
