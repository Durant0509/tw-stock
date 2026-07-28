#!/usr/bin/env python3
"""每日更新 (Windows 排程每交易日 21:30 跑这个)。
流程: 增量抓当日资料 → 重算指标 → 生成网页 → git push。
跨平台。可安全重复跑 (抓取 resumable)。
"""
import os, sys, subprocess, datetime

BASE=os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
PY=sys.executable
LOG=os.path.join(BASE,"update.log")
# 强制子脚本用 UTF-8, 解决 Windows cp950 印中文崩溃
ENV=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass

def log(msg):
    line=f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(LOG,"a",encoding="utf-8") as f: f.write(line+"\n")

def run(script, desc, required=False):
    log(f"▶ {desc} ({script})")
    r=subprocess.run([PY, script], cwd=BASE, capture_output=True, text=True, encoding="utf-8", env=ENV)
    if r.returncode!=0:
        log(f"  ⚠️ {script} exit {r.returncode}: {r.stderr[-300:] if r.stderr else ''}")
        if required: log(f"  ✗ 必要步骤失败, 中止"); sys.exit(1)
    else:
        tail=r.stdout.strip().split("\n")[-1] if r.stdout.strip() else "ok"
        log(f"  ✓ {tail}")
    return r.returncode==0

def git(args):
    r=subprocess.run(["git"]+args, cwd=BASE, capture_output=True, text=True,
                     encoding="utf-8", errors="replace", env=ENV)
    return r.returncode==0, ((r.stdout or "")+(r.stderr or "")).strip()

def main():
    log("="*50)
    log("每日更新开始")
    # 平日才抓 (周末无新资料; 但仍会重算+push 确保网页在线)
    wd=datetime.date.today().weekday()
    if wd<5:
        # 1) 增量抓当日资料 (resumable, 只补没抓过的)
        for s,d in [("pull_data.py","个股量价/PE"),("pull_meta.py","公司资料+殖利率/PB"),
                    ("pull_margin.py","融资融券"),
                    ("pull_finmind.py","台指期法人"),("pull_t86.py","三大法人现货"),
                    ("pull_chips.py","法人筹码快报")]:
            if os.path.exists(s): run(s,d)
    else:
        log("周末, 跳过抓取")
    # 2) 重算指标 + 生成网页 JSON
    ok=True
    ok&=run("dashboard.py","策略健康度")
    ok&=run("gate.py","进场闸门")
    if os.path.exists("chips.py"): run("chips.py","法人筹码计算")
    if os.path.exists("chips_backtest.py"): run("chips_backtest.py","筹码因子回测")
    ok&=run("precompute.py","个股体检",required=True)
    # 3) 组合网页
    run("build_warroom.py","生成作战台网页",required=True)
    # 4) git push (只推程式+网页+成果JSON, data/ 被 gitignore 挡)
    # 先确保 git 身份已设 (没设的话 commit 会 fatal, 曾导致文件卡 staged 却假装 push 成功)
    okn,_=git(["config","user.name"])
    if not okn:
        git(["config","user.name","tw-stock-bot"])
        git(["config","user.email","tw-stock-bot@users.noreply.github.com"])
        log("  ⚙️ git 身份未设, 已自动补上")
    git(["add","-A"])
    ok_commit,out=git(["commit","-m",f"daily update {datetime.date.today():%Y-%m-%d}"])
    if "nothing to commit" in out:
        log("  无变更, 跳过 push")
    elif not ok_commit:
        log(f"  ✗ commit 失败, 中止 (未 push): {out[-300:]}")
        sys.exit(1)
    else:
        # 先 pull rebase 避免远端有更新导致 push 失败
        git(["pull","--rebase","--autostash"])
        okp,outp=git(["push"])
        if okp and "up-to-date" not in outp.lower():
            log("  ✓ push 成功")
        else:
            log(f"  ⚠️ push 未生效(可能需登入GitHub或无新commit): {outp[-200:]}")
    log("每日更新完成")

if __name__=="__main__":
    main()
