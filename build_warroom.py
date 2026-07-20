#!/usr/bin/env python3
"""组合 warroom.html = 模板 + 最新数据。
数据来源: dashboard_data.json + gatelight_data.json + stocks_data.json。
update.py 每日重算那三个 JSON 后, 调这个重生成 warroom.html。
"""
import json, os
BASE=os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)

def ds(t): return t[::5]  # 降采样

dash=json.load(open('dashboard_data.json',encoding='utf-8'))
gate=json.load(open('gatelight_data.json',encoding='utf-8'))
stocks=json.load(open('stocks_data.json',encoding='utf-8'))
dash_slim={'current':dash['current'],'engine':ds(dash['engine']),'cheap':ds(dash['cheap']),'retail':ds(dash['retail'])}
merged={'dash':dash_slim,'gate':gate,'stocks':stocks}
data_js=json.dumps(merged,ensure_ascii=False)

tmpl=open('warroom_template.html',encoding='utf-8').read()
html=tmpl.replace('__DATA__',data_js)
open('warroom.html','w',encoding='utf-8').write(html)
print(f"warroom.html 重生成完成 ({len(html)} bytes, asof {dash['current']['date']})")
