# 台股策略作战台

一套 regime-aware 的台股策略监控系统：**大盘策略切换 + 散户进场闸门 + 个股体检排雷**。
资料来源 TWSE + FinMind，回测 2018–2026、point-in-time、分割调整。

## 🖥️ 网页（GitHub Pages）

- **作战台（主力）**：`warroom.html` — 大盘作战 + 个股体检，每天看这个
- 研究报告（静态）：`strategy.html`（价值动能）、`elliott.html`（波浪验证）、`ls_backtest.html`（散户多空比回测）
- 单项详情：`gatelight.html`（进场闸门）、`dashboard.html`（策略健康度）、`stockcheck.html`（个股体检）

> GitHub Pages 上线后网址：`https://<你的帐号>.github.io/<repo名>/warroom.html`

## 📊 系统逻辑（回测验证过的诚实定位）

| 模组 | 内容 | 验证结论 |
|------|------|---------|
| 策略切换 | 动能引擎(牛市)/撿便宜(熊市防御)/散户反指 健康度体温 | 各 regime-specific，无全天候圣杯 |
| 进场闸门 | 散户多空比 p95 极端偏多→减码 | Sharpe 1.18 vs 纯B&H 1.05 |
| 个股体检 | 前150大 7维度 + 排雷 | 避烂股可靠、选飙股做不到 → 定位排雷工具 |

## 🔄 自动更新（Windows）

### 首次设定
```bat
:: 1. clone
git clone https://github.com/<你的帐号>/<repo名>.git
cd <repo名>

:: 2. 首次全抓三年资料 (约 1-2 小时, 只需一次)
python bootstrap.py
```

### 设定每交易日自动更新
用 **Windows 工作排程器 (Task Scheduler)**：

1. 开「工作排程器」→「建立基本工作」
2. 名称：`tw-stock-update`
3. 触发程序：**每天**、开始时间 **21:30**
4. 动作：**启动程式**
   - 程式：`python`（或 python.exe 完整路径，如 `C:\Python312\python.exe`）
   - 引数：`update.py`
   - 起始位置：**repo 的完整路径**（如 `C:\Users\你\tw-stock`）← 重要
5. 完成。电脑不关机就会每晚自动跑。

> `update.py` 内建判断：周末不抓资料（台股无新资料），平日才增量抓。
> 每次跑会写 `update.log` 可查执行纪录。

### 资料更新时点参考
| 资料 | 官方更新 |
|------|---------|
| 个股量价/本益比 | ~14:30-15:00 |
| 三大法人期货未平仓（散户闸门） | ~15:00 |
| 三大法人现货买卖超（外资连买） | ~15:00-16:00 |
| 融资融券 | ~21:00（最晚）|

→ 设 **21:30** 抓，确保所有资料都上线、一次抓齐最完整。

## 📁 档案结构

```
pull_*.py        各资料源抓取 (resumable)
bootstrap.py     首次全抓
update.py        每日更新 (排程跑这个)
build_warroom.py 组合作战台网页
loader.py ls_loader.py  资料解析
backtest.py 等   回测引擎与因子
data/            历史资料 (8.2GB, .gitignore 排除, Windows 端重抓)
*.html           网页
*_data.json      网页资料 (每日重算)
```

## ⚠️ 免责

本系统为个人研究工具，非投资建议。所有因子经回测验证并诚实揭露限制（详见各研究报告网页）。台股无「选飙股圣杯」，本系统价值在风险过滤与体检排雷。
