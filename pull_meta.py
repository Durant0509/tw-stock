#!/usr/bin/env python3
"""抓基础资料: 上市公司基本资料(产业/股数) + 当日殖利率/股价净值比(BWIBBU_d)。
这两个是 loader/precompute 必需的。每日更新会重抓 (公司资料变动少, BWIBBU 抓最新交易日)。
"""
import os, sys, json, glob, urllib.request, datetime
# Windows cp950 终端印中文会崩, 强制 UTF-8
try: sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')
except: pass
BASE=os.path.dirname(os.path.abspath(__file__)); os.chdir(BASE)
os.makedirs("data", exist_ok=True)
UA={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

import time
def get(url):
    last=None
    for a in range(4):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=40).read().decode())
        except Exception as e:
            last=e; time.sleep(3*(a+1))
    raise last

# 1) 上市公司基本资料 (产业别 + 已发行股数)
try:
    d=get("https://openapi.twse.com.tw/v1/opendata/t187ap03_L")
    new=json.dumps(d,ensure_ascii=False)
    fp="data/company_info.json"
    if not (os.path.exists(fp) and open(fp,encoding='utf-8').read()==new):
        open(fp,"w",encoding='utf-8').write(new); print(f"company_info.json 更新 ({len(d)} 档)")
    else: print("company_info.json 内容相同, 跳过")
    # 月营收(产业中文名对照)也一起抓, loader 需要
    r=get("https://openapi.twse.com.tw/v1/opendata/t187ap05_L")
    rnew=json.dumps(r,ensure_ascii=False)
    fp2="data/rev_latest.json"
    if not (os.path.exists(fp2) and open(fp2,encoding='utf-8').read()==rnew):
        open(fp2,"w",encoding='utf-8').write(rnew); print(f"rev_latest.json 更新 ({len(r)} 档)")
    else: print("rev_latest.json 内容相同, 跳过")
except Exception as e:
    print(f"公司资料抓取失败: {e}")

# 2) BWIBBU_d 殖利率/PB — 抓最近有资料的交易日 (往前试最多10天)
def latest_trading_dates():
    """从 mi_index 已抓的日期取最新几个当候选"""
    ds=sorted(os.path.basename(f)[:-5] for f in glob.glob("data/mi_index/*.json"))
    return ds[-10:][::-1] if ds else []

got=False
for ds in latest_trading_dates():
    fp=f"data/bwibbu_{ds}.json"
    if os.path.exists(fp): got=True; break   # 已有最新的
    try:
        d=get(f"https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date={ds}&response=json")
        if d.get("stat","").lower()=="ok" and d.get("data"):
            open(fp,"w",encoding='utf-8').write(json.dumps(d,ensure_ascii=False))
            print(f"bwibbu_{ds}.json 抓取成功"); got=True; break
    except Exception as e:
        continue
if not got: print("⚠️ BWIBBU 未抓到 (殖利率/PB 会显示—, 不影响主要功能)")
print("DONE meta")
