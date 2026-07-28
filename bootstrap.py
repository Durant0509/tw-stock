#!/usr/bin/env python3
"""首次全抓 (Windows 第一次跑这个, 约 1-2 小时)。
建立完整 data/ 三年历史。之后每日用 update.py 增量更新。
跨平台: 自动切到脚本所在目录, 解决相对路径问题。
"""
import os, sys, subprocess

BASE=os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)   # 关键: 确保所有相对路径 data/xxx 正确
ENV=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass

PULLS=[
    ("pull_data.py",    "个股量价/本益比 (MI_INDEX) ~2500天, 最久"),
    ("pull_meta.py",    "公司基本资料 + 殖利率/PB (loader 必需)"),
    ("pull_margin.py",  "融资融券 ~980天"),
    ("pull_finmind.py", "台指期三大法人 (散户多空比)"),
    ("pull_t86.py",     "三大法人现货买卖超 (外资连买)"),
    ("pull_chips.py",   "法人筹码快报 (现货金额+期货/选择权OI)"),
]

def run(script, desc):
    print(f"\n{'='*60}\n▶ {desc}\n  执行 {script}...\n{'='*60}", flush=True)
    r=subprocess.run([sys.executable, script], cwd=BASE, env=ENV)
    if r.returncode!=0:
        print(f"⚠️ {script} 异常退出 (code {r.returncode}), 继续下一个", flush=True)
    return r.returncode==0

if __name__=="__main__":
    print("首次全抓开始 — 预计 1-2 小时。可中断, 重跑会跳过已抓的 (resumable)。")
    for s,d in PULLS:
        if os.path.exists(os.path.join(BASE,s)): run(s,d)
        else: print(f"跳过 {s} (不存在)")
    print(f"\n{'='*60}\n全抓完成。接着执行 update.py 生成网页。\n{'='*60}")
    run("update.py", "首次生成网页")
