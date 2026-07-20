#!/usr/bin/env python3
"""就地修复被存成 big5/cp950 的 JSON 档 → UTF-8。
不用重抓, 直接转码 (资料是好的, 只是编码存错)。
逐档尝试: 已是UTF-8就跳过; 是big5就读出来用UTF-8重存。
"""
import glob, sys, json
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass

pats=['data/*.json','data/*/*.json','*.json']
fixed=skip=fail=0
for pat in pats:
    for fp in glob.glob(pat):
        # 先试 UTF-8, 能读就跳过
        try:
            open(fp,encoding='utf-8').read(); skip+=1; continue
        except UnicodeDecodeError: pass
        # 试 big5 / cp950 读出来, 用 UTF-8 重存
        done=False
        for enc in ['big5','cp950','big5hkscs']:
            try:
                content=open(fp,encoding=enc).read()
                # 验证是合法 JSON
                json.loads(content)
                open(fp,'w',encoding='utf-8').write(content)
                fixed+=1; done=True; break
            except Exception:
                continue
        if not done:
            fail+=1; print(f"  修不了: {fp}")
print(f"\n修复完成: 转码 {fixed} 档 | 已是UTF-8 {skip} 档 | 失败 {fail} 档")
if fail: print("失败的档建议删掉重抓")
