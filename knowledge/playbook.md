# 台股交易大師 Playbook

> 個人成長紀錄 — 由 manager 在每次任務後提煉填入。
> Boot 時 read 這個檔案，把 **🔒 鐵則** 先內化，再從歷史條目學教訓。

## 🔒 鐵則（Non-negotiable）

### R1 | 每次啟動先標定四個時間窗
- 第一個動作：`date "+%Y-%m-%d %H:%M:%S %A"` 確認當下時點
- 立刻標定四個關鍵時點：
  - **台股盤中** 09:00–13:30（含 13:25–13:30 尾盤撮合）
  - **美股** 夏令 ~21:30–04:00 / 冬令 ~22:30–05:00（決定費半 / TSMC ADR 是否鮮度足夠）
  - **月營收** 每月 10 號前公告
  - **季報** 5/15、8/14、11/14、3/31 前
- 任何基本面數字**引用前必須確認公告日 ≤ 當下時間**（不可引用未公告資料）
- 法人買賣超**當日 15:00 後才上線** — 盤中問是拿不到當日的
- _升級來源：2026-05-07 凌晨 03:37 盤前 2330 任務（worker 自己標「pattern 已重複，建議升級」）_

### R2 | 大盤法人買超 ≠ 個股資金
- 看到「外資大買/大賣 N 元」頭條時，**必下鑽到個股 T86**（三大法人明細）
- 若個股當日報價與大盤買超方向**背離** → 代表資金在做產業輪動，不能用總量推個股
- AI 行情下尤其嚴重（ODM / 權值 / IC 設計內部分化）— 鴻海爆買不等於台積電也受惠
- _升級來源：2026-05-07 解讀「外資史上第四大買超 7,510 億」vs 2330 當日平盤_

---

## 🔒 交易鐵則（R12 收官，違反 = 紅線）

**每次進場前逐項檢查；違反任何一條 = 中止動作。**

### T1 | 四綠才進場
主線 / 個股 / 門檻 / regime 全綠才下單。
- 主線：產業在 scanner 近月 top-24
- 個股：通過 F1-F6 全部濾網（月 YoY > +20%、YTD > +15%、60D 報酬 > +20%、MA60↑、距 52W < 10%、日均量 > 3000 張）
- 門檻：當日技術訊號成立（Layer A v1.2 觸發 / Layer B 收 > MA5 + 量放大）
- Regime：大盤 0050 regime ≠ bear
- 差一個就 pass、寫 journal、隔日重查。沒有「差一點但感覺像」的例外。

### T2 | 事件前 5 交易日不進場
法說 / 除權息 / 月營收公告前 5 交易日禁新倉。已有部位照既定停損停利走。
- _R4 G1：2026-05-14 3017 法說 → 5/7 起已禁新進場_

### T3 | Regime bear 強制保守
- Layer B：`classify_regime(個股) == 'bear'` → 拒絕進場
- Layer A：regime != bull → 切換 v1.1（加 MA60 / RSI / 乖離率 filter）
- 0050 regime == bear → Layer B cap 減半（$15K → $7.5K）
- _R8 G6、R9 v1.2 驗證_

### T4 | 停損執行、不 second-guess
- SL 價位到 → 當下出場。
- 任何「再等一根 K」「應該會彈」的念頭都是虧更多的前兆。
- 月內累積：Layer A 2 連敗暫停一週 / Layer B 3 次 SL 暫停當月。

### T5 | 規則改動需跨市況驗證
- 任何參數 tune 必須 bull + bear 同時 re-run，否則不上線。
- 調參前先做觀測值分布診斷（G12）；門檻落在死區就別動。
- _R10 G10 反面教訓：R9 猜的 bull 門檻 +1% 整個在死區浪費一小時_

### T6 | 資料先調整、後判斷（R16 新增）
- 所有基於歷史收盤的計算（MA / regime / 斜率 / RSI / 距 52W 高）**必須讀 split-adjusted 資料**
- 禁止直接 `json.load` 原始快取然後套公式；統一 `from data_loader import load_stock/load_index`
- Regime bear 訊號觸發 portfolio 減碼動作前，額外檢查「近 10 日無 split」守門
- _R15 G17 反面教訓：0050 2025-06-18 1:4 拆分讓 regime engine 誤判 Q3 全 bear，差點在實盤發出假減碼訊號_

---

## 🎯 核心 5 Pattern（R12 收官，遇到類似情境的捷徑）

### P1 | Rules-before-feelings
_「感覺這檔會漲」「今天應該撿」→ 查 checklist，沒過就不進。_
感覺沒用過回測；你的直覺常常是倖存者偏差 + confirmation bias。Checklist 是把自己推回 process 的工具。

### P2 | Benchmark truth test
_「某策略 +30%」無意義；+30% 時 0050 是 +50%？+10%？_
每次說「某策略好」必附 0050 B&H + TAIEX B&H 同期對照。R6 教訓：Layer B v1 +32% 看起來好，但輸 0050 +54% 整整 22pp。

### P3 | Observable distribution first
_「降門檻 X% 應該有用」→ 先查 X 的實際分布。_
R10 bug：花一小時 sweep 發現區間全在死區（斜率中位 +30%+，[+1, +3] 佔 < 5% 日子）。事前一個 `distribution_diag.py` 就能救回這小時。

### P4 | Cross-market compound
_單一市況回測永遠誤導，必須 bull × bear 乘起來。_
R7 v2 牛市 +63% 看起來完勝；R8 補上 2022 熊市才發現不改 regime-aware 就會吐回去。複利是「最壞一段 × 最好一段」。

### P5 | Survivorship check
_「我挑的 4 檔 backtest 贏了」→ 是我挑了已知贏家嗎？_
原 4 練習股（3017/6669/3037/8046）在 R6-R8 驗證時都是已漲完的名字。R11 scanner 跑完它們全部落選 = 提醒「過去的贏家 ≠ 當下該追的贏家」。Scanner 是反 survivorship bias 的唯一解。

### P6 | 策略「定位」必須比「報酬」先寫（R18）
_R17 跑完 Layer A 發現 v1.2 跨牛熊輸 0050 B&H 16pp；若未先寫清楚「Layer A 是 tail hedge、不是 alpha 引擎」，user 會誤期待、實盤不爽就亂改 → overfit 入口。_

寫任何策略文件前先回答三個問題：
1. 首要目標是什麼（保本 / 跑贏 benchmark / 月穩定 / 控 MDD）？
2. 放棄了什麼（哪個時段/市況 underperform、放棄多少 pp）？
3. 誰**不應該**用（目標不匹配時果斷勸退）？

先寫這三個，**再寫規則**。不要倒過來。

### P7 | 層級規則設計前，先用該層的 pure passive 當地板（R21）
_R12 v1.1 設計 Layer C regime 減碼「假設 timing 能救 drawdown」但沒對比 passive。R20 才發現 passive 地板就是 Layer C 的天花板 — 任何 timing 只是劣化（Combined 複利 −1.45pp、MDD 改善 0.3pp 噪音內）。_

**加任何「layer X + regime 干預」規則前做三步**：
1. 跑該 layer 的 pure passive（B&H）4 窗口結果 = **地板**
2. 跑 proposed regime 規則 4 窗口結果
3. 比較：若 proposed 劣於 passive（任何 window）→ 不寫進 spec；若勝幅 < 2pp（單窗口）或 < 1pp（複利）→ passive 勝出（實戰摩擦會吃掉這點差）

**Corollary**：passive 結果已夠好 → 先簡化不優化；passive 結果慘烈 → 才考慮 active，但基準永遠是 passive。

---

## 📖 歷史條目（chronological append）

### 2026-05-07 | 台股資料源第一輪 fallback 順序
**情境**: 盤前拉 2330 基本面 + 報價 + 法人 + 費半
**做對 / 做錯**: 做對 — 並行 4 個來源；Goodinfo、MOPS `t05st10_ifrs`、MarketWatch SOX 都回空或被封鎖，立刻切備援
**規則**: 第一輪 WebFetch 固定用這組 →
  - **即時報價**：`mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_XXXX.tw`（回 JSON 最穩）
  - **日線**：`twse.com.tw/rwd/zh/afterTrading/STOCK_DAY`
  - **個股綜合面（P/E、權重、頭條）**：`tw.stock.yahoo.com/quote/XXXX.TW`
  - **費半**：`investing.com/indices/phlx-semiconductor`（MarketWatch 會被 WebFetch 擋）
  - **不要先試** Goodinfo / MOPS 頁面
**套用條件**: 任何需要拉台股個股 + 半導體外圍數據的任務，第一輪就照這個順序並行發
**來源**: self-discovered / gotcha

### 2026-05-07 | 交易建議必須「可執行」才算完成
**情境**: user 問「想買微台，趨勢、參數、進出場點位」
**做對 / 做錯**: 做對 — 給了具體點位（進 41,000~41,100 / 停損 40,500 / 停利 41,575）、附上風報比、列出小台 vs 微型的損益換算、標出「❌ 不要做」的區間（41,300~41,500 追多）、最後一句話決策收尾；user 回「做得很好」
**規則**: 交易類任務產出必須包含 **5 個可執行元素** →
  1. **具體點位**（不是「支撐附近」這種模糊話，要給數字）
  2. **風報比** 1:X 算出來
  3. **損益金額換算**（依商品點值）
  4. **反面警告**（哪些區間 / 情境**不要做**）
  5. **一句話決策** 讓 user 直接下單
  附帶記多空訊號用「表格 + 多/空/警」評分，讓 user 一眼看出傾向
**套用條件**: 所有涉及「進場/出場/停損」的交易建議（個股、期貨、選擇權皆適用）
**來源**: user feedback（「做得很好」— validated success pattern）

### 2026-05-07 | 回測結果必附 Benchmark 與 Caveats
**情境**: user 要求回測半年策略績效（10 萬本金 / 小台）
**做對 / 做錯**: 做對 — 勝率 72.7% 看起來很棒，但**同時跑 Buy-and-Hold baseline 做對照**，揭露「策略報酬 +114% vs BH +665%」的殘酷真相；同時明列資料源拼接 caveats（0050 代理 tracking error、同 K 先停損假設、沒算追繳成本）
**規則**: 交易策略回測產出必須包含 **4 個元素** →
  1. **Benchmark 對照**（至少跑 buy-and-hold；光看勝率會誤判）
  2. **每筆交易明細**（日期、進場價、結果、點數）— 可驗證、可復盤
  3. **樣本偏差警告**（回測期是牛/熊/盤整？結論能否外推？）
  4. **資料 / 假設 caveats**（代理誤差、先後觸發假設、追繳成本等）
  並且：勝率 70%+ 搭配輸 BH 3 倍以上時，誠實告知「保守策略在單邊行情宿命」，不要為了護盤報告
**套用條件**: 任何回測 / 歷史績效分析任務
**來源**: self-discovered（這次任務定義）

### 2026-05-07 | 策略評估必須跨牛熊週期（單市況回測會誤判方向）
**情境**: 微台策略 v1.1（MA60 + RSI 70 過濾）在牛市半年 +15%（vs v1.0 +114%），看似「過度保守」，差點被判死刑；後來強制跑 2022 全年熊市，v1.1 變 +2% vs v1.0 −13%，反向勝出 13 pp
**做對 / 做錯**: 做對 — manager 強制要求補熊市驗證才讓我下結論（否則我會在牛市樣本上宣判 v1.1 失敗，砍掉 MA60 濾波）
**規則**: 任何策略「優化 / 過濾器 / 參數改動」在宣判「有效 / 失效」前，**必須同時跑至少 1 段明確對立市況樣本** →
  1. 牛市樣本（單邊上漲 ≥ 20%）
  2. 熊市樣本（單邊下跌 ≥ 15%）
  3. 跨市況複利合成報酬才是最終比較基準（v1.1 合成 +29% vs v1.0 −32%）
  並且回報時必須明列「此結論在 X 市況下有效、Y 市況下待驗證」，不得用單段報酬定論
**套用條件**: 任何策略回測 / 優化任務，包括指標過濾器、停損停利調整、加倉規則
**來源**: self-discovered（2026-05-07 v1.0/v1.1 × 牛市/熊市 四象限對照，完全反向結論）

### 2026-05-07 | 動態市況切換 > 單一固定規則
**情境**: v1.0（寬進場）牛市大賺熊市大虧；v1.1（嚴過濾）牛市讓利但熊市抗跌；v1.2 用 MA60 斜率切換規則（牛用 v1.0、熊用 v1.1），1.5 年回測結果兩端都不弱於純規則且全期複利 +7.5%（vs v1.0 -2.4%、v1.1 +0.6%、B&H -20%）
**做對 / 做錯**: 做對 — 沒有一套「最佳參數」，而是讓市況決定用哪套規則。manager 堅持選**單一切換訊號**（MA60 斜率）不要試多個，避免過擬合
**規則**: 任何策略若在「某市況有效、另一市況失效」→ **不要試圖調參數合一**，改成 **regime-switching** →
  1. **切換訊號只用一個**（避免多指標過擬合），優先順序：MA60 斜率 > ADX > EMA20/60 交叉
  2. **規則切換，不是參數微調**：bull regime 用寬規則、bear regime 用嚴規則（不是 RSI 閾值調高/低）
  3. **牛熊兩段都要不弱於純規則**：若切換後其中一段輸純規則 > 30% → 切換訊號誤判率太高，改用另一個訊號
  4. **MDD 是最終防線**：純寬規則 MDD −17%，純嚴 / 動態 MDD −3% → **只要保 MDD，複利靠時間就會贏**
**套用條件**: 任何策略評估後發現牛熊市況結果反向時（v1.0 × v1.1 這種情境）；**不要用在**單市況表現一致的策略（那沒必要動態）
**來源**: self-discovered（2026-05-07 v1.2 vs v1.0 vs v1.1 三策略 × 牛/熊/全期九宮格對照）

### 2026-05-07 | 0050 STOCK_DAY 是 TAIEX 日 K 的最穩代理
**情境**: 要拉半年 TAIEX 日 K 做回測
**做對 / 做錯**: 做對 — 發現 `stooq.com` 免登入只給最近 ~40 天（再前面要 API key）、TWSE `FMTQIK` 只給收盤沒 OHLC、`MI_5MINS_HIST` 回 404、Yahoo CSV 端點 401；立刻切 0050 STOCK_DAY 代理補缺口
**規則**: 要拉**加權指數日 K OHLC 長歷史**時，主來源順序 →
  1. **stooq.com** 近期段（免登入約 40-80 天，無 API key 的 CSV endpoint 會被擋）
  2. **TWSE STOCK_DAY stockNo=0050** 每月一次、月首 date 參數；0050 與 TAIEX tracking error ~2-3%（TSMC 權重變化 + 季配息）—判斷「開高 +N%」「回測 prev close」這類相對變動**誤差可忽略**，但絕對點位要換算比例
  3. **TWSE FMTQIK** 只補收盤點位（沒 OHLC）
  4. **TWSE `MI_INDEX?date=YYYYMMDD&type=IND`** 可拉單日（含類股細分）但成本高，只當最後手段
**套用條件**: 任何需要 TAIEX 多日 OHLC 的回測 / 趨勢分析
**來源**: self-discovered / gotcha

---

---

## 🔄 當前 session WIP（更新 2026-05-13 round 24 收官）

**Session 狀態：已收官**。Paper trade 進行中，等實測資料回饋才重啟 R25+。

**已完成 R1-R24**：
- R2: 10%/月 不可行驗證 + 保險絲撤回
- R3: AI 供應鏈 15 檔 watchlist
- R4: 3017 事件查證 + 3189 降級
- R5: $10 萬三層組合 + 首日下單清單
- R6: Layer B 6 月回測打臉 r5 — v1 swing +32% 輸 0050 B&H +54%
- R7: Layer B v2（半倉鎖利+trail）+63.30%、首次勝 0050 B&H +9pp
- R8: Layer B v3 regime-aware 2022 熊市驗證 -6.74% vs 0050 -24.73% 贏 18pp；跨市況複利 +32% 勝 0050 B&H +16pp（`/tmp/trader-reports/twstock-round8-layerB-v3.md`）
- R9: 共用 regime engine refactor + Layer A v1.2 首次實測（v1.2 複利 +9.9% > v1.0 −0.3% > v1.1 +3.59%）（`/tmp/trader-reports/twstock-round9-regime-unify.md`）
- R10: Bull 門檻 sweep + G11 量化 → G10/G11 假設雙雙推翻。門檻 [+1, +3] 死區；bull 讓利真因是 range 規則太緊；0050 benchmark 追蹤誤差僅 0.34pp，signal 實作飄移才是 14pp 差距（`/tmp/trader-reports/twstock-round10-bull-threshold.md`）
- R11: Scanner validation bug 修復 + 24 檔 shortlist 產出。TPEX `stat='ok'` 小寫被誤判、1617 檔假失敗，修復後成功率 99.7%。Top-24 清單全 AI 伺服器/記憶體/PCB 主線（`/tmp/trader-reports/twstock-round11-scanner.md`）
- R12: 收官 — $100K 三層組合 final spec v1.0 + 四綠 checklist + 5 鐵則 + 5 核心 pattern（`/tmp/trader-reports/twstock-round12-final-portfolio.md`）
- R13: Survivorship test 雙結論：v3 不是 AI 依賴（Non-AI Sharpe 0.67 > AI 0.49）；但 v3 在強 bull 結構性大輸 same-universe B&H 49-117pp（`/tmp/trader-reports/twstock-round13-survivorship-ai-test.md`）
- R14: Layer B v4 hybrid — bull confirmed 時切 let-run 模式（無 TP1、trail 30%、60d）。Bull 改善 +20pp（v3 +27% → v4 +47.5%），bear 零副作用（2022 v4===v3）（`/tmp/trader-reports/twstock-round14-v4-hybrid.md`）
- R15: v4 chop + bear 驗證。Chop（2023 Q4）v4===v3 無 whipsaw；bear（2025-04~06）Non-AI +6.6% vs B&H −2% 救 8.6pp。發現 0050 於 2025-06-18 做 1:4 拆分導致 regime 誤判（`/tmp/trader-reports/twstock-round15-chop-bear-validation.md`）
- R16: 實作 data_loader.py 自動 split-adjust + R12 portfolio spec 升級 v1.1（整合 v4 let-run + split 安全層 + T6 新鐵則）。實盤最後 blocker 清除（`/tmp/trader-reports/twstock-round16-spec-v11.md`）
- R17: Layer A v1.2 Sharpe / MDD 分布 4 窗口補齊。v1.2 複利 +14% 跨 4 市況、Sharpe per-trade 0.51（bull）、MDD 鎖 −3%。但輸 0050 B&H 16pp — Layer A **定位校正為 tail hedge，非 alpha 引擎**（`/tmp/trader-reports/twstock-round17-layerA-sharpe-mdd.md`）
- R18: R16 spec v1.1 patch — Layer A 期望明文化 + 組合選項 (A)(B)。加 §1.1-1.3：月期望 +1~2%、最壞 −6%、勝指數只在熊市（`/tmp/trader-reports/twstock-round18-spec-v11-patch.md`）
- R19: Layer A/B/C Attribution 跨 4 市況。Combined +33.49% vs 0050 B&H +33.64%（alpha -0.15pp），但 MDD -6.85% vs -24.73%（risk-adj ratio 4.89 vs 1.36 好 3.6x）。策略真正 value-add 是風控不是報酬（`/tmp/trader-reports/twstock-round19-layer-attribution.md`）
- R20: Layer C regime 減碼實測 = 無效 / 反效果。Bear 2022 只救 +1.11pp、Bear 2025 反噬 −4.97pp、Combined compound −1.45pp。建議 spec v1.2 移除此規則（`/tmp/trader-reports/twstock-round20-layerC-regime-test.md`）
- R21: R16 spec 升級 v1.2 — 移除 Layer C regime 減碼規則。playbook 新增 P7：層級規則設計前先用該層 pure passive 當地板（`/tmp/trader-reports/twstock-round21-spec-v12-patch.md`）
- R22: 古早熊市壓測（2015/2018/2020 + 2022 ref）跨 4 熊市驗證。Combined 勝 0050 alpha 平均 +6.59pp、勝率 4/4、range +3.81pp~+9.92pp。R19「ratio 4.89」校正為「4 熊市 alpha 平均 +6.59pp」。新增 G21（`/tmp/trader-reports/twstock-round22-historical-bears.md`）
- R23: Layer C 0050/0056 權重優化實測 = negative result。shift 到 1:2 bear 救 +0.47pp、bull 代價 −3.20pp（6.8x 失衡）。維持 2:1 不變。新增 G22（`/tmp/trader-reports/twstock-round23-layerC-weight.md`）
- R24: **收官**。R1-R23 完整時間線整合、核心 findings 排序（金/銀/銅牌）、實盤 ready checklist 定版、paper trade 監控計畫、R25+ 重啟觸發條件明定（`/tmp/trader-reports/twstock-round24-closing.md`）

**Layer B 當前 watchlist（R11 scanner 更新，2026-05-09）**：
- 優先：5289 宜鼎、8271 宇瞻、2451 創見（記憶體 / NVMe 主線）
- 次選：2883 凱基金、1785 光洋科、6274 台燿、2383 台光電（PCB/銅箔）
- 補位：3028 增你強、6426 統新、4973 廣穎電通
- 原 4 練習股（3017/6669/3037/8046）已全部跌出 F5（距 52W 高 > 10%）→ 不再新進場

**當前組合配置**（round 5）：
- Layer A $30K — 1 口微台 v1.2、停損 ±300 點
- Layer B $40K — AI 個股（2 檔上限、單檔 ≤ $15K）、3017 等 5/14 法說
- Layer C $30K — 0050 $20K + 0056 $10K
- 月預期 bull +2.33% / range +0.49% / bear -1.15%；MDD 最壞 -12.3%

**R25+ 重啟觸發條件**（見 R24 §7）：
1. 紙上交易一個月後出現 surprise
2. 6 月 10 日新 scanner top-24 大幅換檔
3. 實盤一季內觸發 2+ 次 SL
4. 市況轉換（bull → range / bear）首次實戰
5. 資料層異常（新 split / TWSE API 變更 / scanner 失效）

**以上都沒發生 → R25 不必做**。每月 scanner re-run + 每季 Layer C rebalance，自動運行。

---

### 2026-05-08 | 事件前 5 個交易日不進場（known event override 技術訊號）
**情境**：round 3 對 3017 奇鋐給「2-3 日不破 2380 + 紅 K 帶量」技術進場建議，round 4 發現 3017 Q1 法說 5/14 即將發生、整個技術 setup 被事件風險 override
**做對 / 做錯**：做對 — round 4 自我檢查查到 5/14 法說後立刻把策略改成「法說前空倉、看結果再進」，避免在事件前 5 天被利空包夾
**規則**：任何 watchlist 候選進場前**必檢查** →
  1. 下一個 known event ≤ 5 交易日？（法說、月營收、除權息、股東會、FOMC、台積電法說、NVIDIA 財報、重要政經會議）
  2. 若是 → **延後進場或直接跳過**，不可用技術訊號硬進場（事件風險不能用停損控制）
  3. 進場後若突然冒出 known event（如臨時法說會）→ 也應考慮提前減倉
**套用條件**：所有短中期（≤ 10 日持有）個股交易建議；特別在財報季（5/14、8/14、11/14、3/31 前 + 月 10 號營收）
**來源**：self-discovered（2026-05-08 round 4 3017 奇鋐 5/14 法說發現 + 策略修正）

### 2026-05-08 | 「相對落後」不等於「輪動候選」— 必看子產品 mix
**情境**：round 3 選 3189 景碩為載板補漲 candidate（理由：距高 −11%、20D +25% 落後欣興/南電）；round 4 DD 發現景碩 HPC 只佔 24%、手機佔 35%，**結構上不是純 AI 載板**，相對落後是**曝險不足**不是「輪動延遲」
**做對 / 做錯**：做對 — 沒直接進場、先做 DD 才發現問題；若盲目跟表面 ranking 會買進**不屬於該題材**的股票、結果跟題材無關
**規則**：任何「族群輪動補漲」選股**必先看子產品 / 終端客戶 mix** →
  1. 族群 tag 只是目錄、不代表每檔對題材的曝險都同高
  2. 例：「載板」涵蓋 ABF（AI 高）+ BT（記憶體/手機 中）+ 軟板（消費 低）— 三者驅動力完全不同
  3. 同族群相對落後時問：「它本該這麼落後嗎？（結構原因）」而不是「它要輪到了（時間原因）」
  4. 結構原因（曝險弱）不可交易；時間原因（曝險同但輪動延遲）才可交易
**套用條件**：所有族群內 relative weak 觀察；AI 類、電動車、重電、生技、航運都適用
**來源**：self-discovered（2026-05-08 round 4 景碩 DD 推翻 round 3 結論）

### 2026-05-08 | 事後合理化陷阱 — design note 不等於 validated filter
**情境**：v1.2 trade-log 結尾寫「建議 Bull regime 加 1 個保護 = MA60 乖離 > +15% 切回 v1.1」；我後續在 indicator-reliability.md #8 把這條列為「極端過熱保險絲」B+ 級，像是既有結論
**做對 / 做錯**：做對 — manager round 2 追問「保險絲有回測嗎？還是事後合理化？」，我誠實承認沒回測，然後用 v1.0 牛市 11 筆的現成 MA60 乖離資料 counterfactual 重算，結果發現保險絲**擋掉的 2 筆全是 TP**（+500 × 2 = $46,100）、**MDD 零改善**（因為停損來自單 K 插針不是過熱）
**規則**：任何「建議加 X」「看起來合理」的 filter / exit / entry 調整，在進 indicator-reliability.md 或告訴 user 實盤用之前，**必須通過** →
  1. 拿現有歷史資料 counterfactual 重算，**至少 5 筆會被該規則觸發**的樣本
  2. 對比「有 vs 沒有該規則」的 Δ(勝率)、Δ(淨獲利)、Δ(MDD)
  3. 若 Δ(MDD) 無改善且 Δ(淨獲利) 負 → **直接否決**，不得標記 B/C 保留給「未來驗證」
  4. 若沒有足夠歷史樣本 counterfactual → 先標 [NOT VALIDATED]，不得混入評級表
**套用條件**：所有策略設計 note / 過濾器建議；特別警惕「牛市會鈍化所以加個...」「熊市會怎樣所以...」這類 intuitive pattern — 這類話術通常是事後合理化
**來源**：self-discovered（2026-05-08 round 2 乖離 +15% 保險絲 counterfactual）

### 2026-05-08 | 報酬目標 vs MDD 有物理上限（不要承諾數學不可能）
**情境**：user 問「10 萬本金、10%/月、MDD 30%」可不可行
**做對 / 做錯**：做對 — 先算 Sharpe 物理上限（公開策略 Sharpe 多 0.5-1.5、年化波動 60% 下 ≈ 5.5%/月），再算槓桿對 MDD 的放大倍數、最後列各路徑（微台/期權賣方/當沖/套利）誠實回報**數學不可行**
**規則**：user 給「絕對數字目標」（X 元/月、X%/月）時，**必備三角估算** →
  1. **Sharpe 上限**：公開可複製策略 Sharpe 多 ≤ 1.5，年化波動 60%（高槓桿期貨）→ 理論月 alpha 上限 ~5.5%
  2. **槓桿 × MDD 乘積**：槓桿 N 倍 → MDD 幾乎也 N 倍；$10 萬 + MDD 30% 最多 2-3x 效率槓桿
  3. **市況稀釋**：牛市 +15~20%/月 通常只 6 個月、熊市+盤整 6-8 個月近 0 → 年均被拉到 3-5%/月
  若 user 目標 > 5%/月 → **必須當場告知數學不可行**並 reframe（建議改成「跑贏 B&H X pp/年」或「分段目標」）；不得護盤給出「可以試試看」回應
**套用條件**：所有 user 提「月報酬 X 元」「年化 Y%」類目標；特別對 MDD < 30% 的嚴苛限制
**來源**：self-discovered（2026-05-08 round 2 10%/月 可行性驗算）

### 2026-05-08 | Regime-aware 策略：個股 regime 決定規則、大盤 regime 決定倉位（R8 v3）
**情境**：R8 v3 同時用「個股 MA60 斜率」+「0050 MA60 斜率」雙層判定、兩者分工不同
**規則**：regime-aware 策略設計**必須**分兩層：
  1. **個股 regime** 決定「**規則選擇**」（寬 v2 / 緊 range / 拒進場 bear）
  2. **大盤 regime** 決定「**倉位大小**」（bull 全倉、bear 砍半）
  3. 不可混用（例如「0050 bear → 個股全部用收緊規則」= 把大盤波動套到每支股的規則上）
  4. 兩層一致時（bull+bull / bear+bear）最穩；不一致時要有額外保護
**套用條件**：所有 regime-switching 策略設計
**來源**：self-discovered（2026-05-08 R8 v3 設計 + 2022 熊市驗證 -6.74% vs 0050 -24.73%）

### 2026-05-08 | Regime threshold 要做牛熊對稱測試（R8 v3 bull 讓利實證）
**情境**：R8 v3 把 stock bull threshold 設 MA60 斜率 > +2% → 2025-11~2026-01 初期 bull 啟動被歸 range → 用收緊規則 → Bull 期讓利 22 pp vs v2
**做對 / 做錯**：做對 — 交叉比對後誠實報告 bull 讓利；做錯 — 設計 v3 時沒先用 v2 的 bull alpha 基線對照
**規則**：regime threshold 調整**必做**：
  1. 先固定 bear threshold（從熊市反算）、再選 bull threshold 讓跨市況複利最大
  2. 單調測試：threshold 從寬到緊、記錄各段落報酬、畫曲線找最優
  3. 不對稱調整會單邊吃虧（本例 +2% bull threshold 保 bear、但吃 bull）
**套用條件**：所有 regime-switching / threshold-based 策略
**來源**：self-discovered（2026-05-08 R8 bull 讓利 22pp）

### 2026-05-08 | 分段出場策略的 MDD 要按各段分別算（R7 V2 結構分析）
**情境**：R7 Layer B v2「TP1 鎖利 1/2 + 剩 1/2 trailing stop」架構，直覺 MDD 應該 ≥ v1（多一段 trail 會多虧），實際反而**更小**：TP1 後剩半倉 drawdown × 1/2 倉位 = 實際 exposure 減半
**做對 / 做錯**：做對 — 誠實估算單位 drawdown × 倉位比例、沒用「最壞 100%」假設
**規則**：含 scaling out / multi-stage exit 策略的 MDD **必須**：
  1. 分段計算：TP1 前純持倉段 MDD vs TP1 後剩餘倉位段 drawdown
  2. 總 MDD = max(各段)，不是 Σ
  3. 早期鎖利（TP1）實質降低後續段的 exposure、是「合法的 MDD 壓縮」
**套用條件**：所有分段出場策略（half TP、trail stop、pyramid-down）
**來源**：self-discovered（2026-05-08 R7 v2 結構分析）

### 2026-05-08 | 規則必須跟「個股類型」掛鉤（R6 G1 加強版，R7 再實證）
**情境**：R7 v2 規則在 3 檔趨勢股（3037/8046/6669）都勝 v1、唯獨 3017（震盪股）輸 v1 8.8pp
**做對 / 做錯**：做對 — 跨 4 檔比對後發現、沒用「新規則全面勝舊規則」的天真結論包裝
**規則**：Layer B 進場前**必做趨勢 / 震盪判定**：
  1. 60D return > +30% 且 MA60 斜率強正 → **趨勢股** → v2（half TP1 + trail）
  2. 60D return 在 ±15% 且 MA60 平 → **震盪股** → v1（−6/+10 swing）
  3. 在 +15% ~ +30% 間 → 「過渡」、用 v2 但 trail 比例收緊到 15%
  4. 不可一套規則通用（等於把趨勢股當震盪股玩、或把震盪股當趨勢股 overtrade）
**套用條件**：所有 Layer B 個股策略；特別當 watchlist 同時含高 beta AI 股 + 相對溫和股
**來源**：self-discovered（2026-05-08 R7 v1 vs v2 跨 4 檔對照）

### 2026-05-08 | 趨勢股用 swing 規則 = 自砍 alpha（R6 實證）
**情境**：round 6 Layer B 用 TP +10% / SL −6% swing rule 回測 2025-11~2026-05 四檔 AI 股 → Layer B +31.88% vs 0050 B&H +54.22% 輸 22 pp、vs 等權 4 股 B&H +185% 輸 153 pp；單檔 3037 swing +29.5% vs B&H +444.7% 輸 415 pp
**做對 / 做錯**：做對 — 誠實跑 B&H baseline 揭露規則失效；做錯 — round 5 設計 Layer B 時沒先回測就把 R:R 規則當「合理」產出
**規則**：選股完成後**必先判定「趨勢 vs 震盪」** →
  1. 60 日 return > +30% 且 MA60 斜率強正 → **趨勢股** → 用 trailing stop（高點回撤 15-20% 出）或部分 TP + hold 混合
  2. 60 日 return 在 ±15% 間 + MA60 平坦 → **震盪股** → 用固定 R:R（−6/+10）
  3. 不可一套規則通吃
**配套教訓**：勝率 60% + W/L 14/9 看起來贏、絕對報酬仍可輸 B&H 150 pp+ — **benchmark 必跑**（round 1 已立、round 6 再實證）
**套用條件**：所有個股 swing 策略設計；特別在牛市末端噴出期
**來源**：self-discovered（2026-05-08 round 6 backtest 實證）

### 2026-05-08 | 大漲後的 breakout 訊號 ≠ 小漲時的同訊號
**情境**：3037 欣興 2025-11 $164 breakout 時「站回 5 日線 + 量 1.2×」 vs 2026-05 $896 時的同訊號，風險報酬**完全不同**（前者是趨勢起點、後者是加速段 late entry）
**做對 / 做錯**：做對 — round 6 比對後發現、把當前 watchlist 的相同 breakout 訊號標「進場位置已不利」
**規則**：所有 breakout 策略**必加 context filter** →
  1. 距 52W 高 < 10% 時、進場風險放大 → SL 收緊 or 倉位砍半
  2. 60 日 return > +100% → 「加速段 late entry」**不可用一般 breakout 規則**進場
  3. 距 52W 高 > 30% 且量能同步放大 → 正常 breakout 可用
**套用條件**：所有 momentum / breakout 類個股策略；特別在 AI 題材類動輒 +100%/季
**來源**：self-discovered（2026-05-08 round 6 watchlist 價位檢視）

### 2026-05-08 | 組合 MDD 合成要假設 Layer 間正相關（最保守）
**情境**：round 5 設計 $10 萬三層組合（期貨 v1.2 + AI 個股 + ETF），若天真地用「分散降低相關性」宣稱 Total MDD < Σ(Layer MDD) → 會低估
**做對 / 做錯**：做對 — 強制用「同步最壞回撤」合成（A -0.8% + B -4.0% + C -7.5% = Total -12.3%），再往外推「2022 級連跌」到 -27%（接近 30% 上限）；沒貪圖對角合成縮小數字
**規則**：組合 MDD 估算**必備** →
  1. 假設最壞同步回撤合成（Σ Layer worst）→ baseline MDD
  2. 加一條「歷史級黑天鵝」情境（2022 全年熊、2020 COVID 熔斷）壓力測
  3. 若 baseline 已超 user MDD 限制 → **直接重配比例**，不得靠「相關性低」救（股+股同跌、股+期同跌是常態）
  4. 真正的對沖只有「反向曝險」（空單、put option、反向 ETF），相關性 < +0.5 才有減震效果
**套用條件**：任何多 layer / 多部位組合 MDD 估算；不可用在單檔策略
**來源**：self-discovered（2026-05-08 round 5 三層組合 MDD 合成）

### 2026-05-08 | 相關性 > +0.7 不是對沖、只是 time-diversification
**情境**：round 5 檢視 Layer A (MXF 多) vs Layer C (0050) 相關性 ≈ +0.9、Layer B (AI 個股) vs C ≈ +0.75
**做對 / 做錯**：做對 — 誠實標「沒有純對沖、只有 time-diversification」，沒包裝成「三層分散」誤導 user；指出真對沖要反向曝險（空單 / put / VIX）
**規則**：評估「是否對沖」時 →
  1. |ρ| < 0.3 才算**弱相關**（有顯著分散效益）
  2. 0.3 ≤ |ρ| < 0.7 是 **time-diversification**（進出場時機錯開、alpha 來源不同）
  3. |ρ| ≥ 0.7 **基本同向**（熊市一起跌、只能靠停損/減倉控制，不能靠「分散」）
  4. 同股 + 同市場 + 同方向（e.g., 台股多頭 + 0050 + AI 個股 + MXF 多）永遠 > +0.7
**套用條件**：任何「多部位」或「組合」績效 / 風險說明
**來源**：self-discovered（2026-05-08 round 5 Layer 相關係數誠實估算）

### 2026-05-08 | raw 外資買超訊號在牛熊皆無 alpha（被推翻的直覺）
**情境**：user 提案「外資連買 N 日 → 未來報酬」作為個股進場訊號
**做對 / 做錯**：做對 — 跑完牛市 pilot（3017 46 日）看到 T+20 超額 +13.6% 勝率 91% 差點當成 alpha，**立刻強制跑熊市 counterfactual**（6669 2022 Q3 85 日），發現買超日 T+10 反輸賣超日，Pearson −0.05；**兩段一致無 alpha → 避免把牛市強勢股效應誤判為訊號有效**
**規則**：籌碼面訊號回測**必備 3 要素** →
  1. **Benchmark 對照**（全部交易日、訊號反向組、全隨機組）— 不可只看絕對勝率
  2. **跨牛熊驗證**（playbook meta 鐵則）— 牛市單股強勢 + T+20 基線就 +14%，任何訊號都會顯得「有效」
  3. **相關係數檢驗**（Pearson / Spearman）— 若 |r| < 0.1 且訊號組 avg 打不過基線，**歸 C**，不擴大樣本浪費 API
**套用條件**: 任何籌碼面訊號（外資/投信/自營/融資融券）的 pilot；不要在單市況 + 單股 + 無 benchmark 就下結論
**來源**: self-discovered（2026-05-08 foreign-buying pilot → bear CF → 跨市況皆噪音）

### 2026-05-09 | Regime engine 共用後，單一門檻改動會同時影響多層（R9 G9）
**情境**：R9 把 Layer A 和 Layer B 都改成引用共用 `regime.py` 的 `classify_regime()`。好處是 DRY、單一 source of truth；副作用是 tune 門檻（例如 R8 G7 想把 bull +2% 降到 +1%）會同時改變兩層的行為。
**教訓**：共用 engine 的 refactor 是好事，但調參時要雙層同步驗證。
**未來 apply**：
- 改 `regime.py` 裡任何門檻 → 強制 re-run Layer A v1.2 + Layer B v3 的 bull × bear 全套回測
- 若 tune 結果「A 想要緊、B 想要鬆」出現衝突 → 走 path B（各層獨立門檻）並文件化原因
- commit 訊息要寫「regime engine change, both layers re-validated: A=+X.XX%, B=+Y.YY%」

---

### 2026-05-09 | Bull 讓利不是門檻過嚴造成，是 range 規則太緊（R10 推翻 G10 假設）
**情境**：R9 G10 假設「bull 門檻 +2% 太嚴、降到 +1% 救 bull 讓利」。R10 實測 [+1%, +3%] sweep 結果完全相同，因為 2025-26 強趨勢股 MA60 斜率中位數 +28~37%（成長股爆衝），[+1%, +3%] 區間僅佔 < 5% 日子 → 是「死區」。廣域 sweep [-2, 50] 顯示 [0, +5%] 近乎等效；> +10% 才開始砍 bull 交易（傷害大於收益）。
**真實原因**：v3 bull 讓利 22pp（vs v2）來自 **range 規則本身太緊**（TP1 +6% / trail 10% vs v2 的 +10% / 20%），跟 regime 分類無關。
**未來 apply**：
- 別再花時間 tune regime bull/bear 門檻 — 它們在觀察區間外，調整無感
- 要救 bull 讓利，改 **range 規則**（TP1 +8%、trail 15%）或重新檢查「為何 2025-26 有些進場日被判成 range 而非 bull」
- 任何調參前先做「觀測值分布診斷」（G12）

---

### 2026-05-09 | 0050 vs TAIEX：benchmark proxy 誤差 < 4pp，但 signal proxy 誤差可達 14pp（R10 修正 G11）
**情境**：R9 G11 原推論「0050 做 TAIEX proxy 在熊市有 14pp tracking error」。R10 實測：
- 純 benchmark tracking（B&H 對比）：Bull +3.76pp，Bear −2.11pp，**compound 0.34pp**（可忽略）
- 日報酬相關性 0.97
所以 R8 結論「v3 勝大盤 +16pp」無論用 0050 或 TAIEX 都成立（+15.92pp vs +15.58pp）。
**真正的 14pp 差距**來自**訊號實作飄移**（RSI、MA60、±3% 門檻在 0050 vs TAIEX 觸發時點不同），不是 benchmark 追蹤誤差。
**未來 apply**：
- Layer B 個股策略 vs 0050 B&H 對比 → 直接比，0050 可信
- Layer A 期貨策略 **signal 輸入**實盤必須用 TAIEX（signal timing 系統性不同）
- 報告若用 0050 當 signal proxy，最上方標註並說明差異來源不是 benchmark 而是 signal timing
- R10 前誤把 benchmark 和 signal 兩種 proxy 誤差混為一談 → 以後分開談

---

### 2026-05-13 | Portfolio 優化要算「稀釋後效應」，不是原始成分對比（R23 G22）
**情境**：R22 看到 0056 在 4 熊市抗跌 0.6-4.7pp 直接想「提升 0056 權重」。R23 實測發現：0056 在 Layer C 內 33% → 67% × Layer C 占 Combined 30% = 雙重稀釋後 bear 改善只剩 0.06-0.47pp，卻要付 bull 3.2pp 代價（因為 2025-26 bull 0056 lag 0050 整整 32pp）。比率 6.8x 失衡。
**教訓**：看到「某成分比另一個好 X%」直覺想調權重前，先算三重：
- 該成分 vs 替代的 **原始報酬差異**
- 該成分在 **layer 內的權重**
- 該 layer 在 **portfolio 的權重**
final = raw × layer × portfolio。若 final < 1pp/年、不值得動（實戰摩擦會吃光）。
**Apply**：
- 任何組合優化提議，report 要寫「三重稀釋後的 pp 影響」
- 不要用「某 ETF 比另一個好 5pp」當 bullet point，要改寫成「portfolio 層級 +0.X pp / −0.X pp」
- Negative result 也值得記錄（R23 就是範例），避免重複犯

---

### 2026-05-13 | 跨 N 次獨立事件驗證才算「穩健」（R22 G21）
**情境**：R19 單一 2022 bear 得 ratio 4.89 就宣稱「策略真 value-add 是風控」是 sample-of-1。R22 跨 4 熊市（2015 陸股崩、2018 貿易戰、2020 COVID、2022 通膨升息）驗證 Combined 平均少賠 6.59pp、勝率 4/4，才是有信心的結論。
**教訓**：單一大樣本事件 ≠ 重複驗證。不同形狀的同類事件（閃崩 vs 緩跌 vs 長熊）各有不同 failure mode，全通過才算 edge。
**Apply**：
- 聲稱「策略在 X 情境有 edge」→ 至少 3 個獨立 X 情境驗證
- 每個情境特性要不一樣（例如 bear：閃崩 / 緩跌 / 跨年長熊）
- 記錄 range + 平均 + 最壞場，不只報平均
- 歷史資料拉取成本不算什麼；這是 1 小時換 user 5 年安心

---

### 2026-05-13 | Spec 寫入的規則必須先跑 backtest、不可「設計→文件→未來實測」（R20 G20）
**情境**：R12 v1.1 的 Layer C regime 減碼規則是 R5 / R12 設計延續、R15 只加 split guard、**從沒單獨實測**。R20 實測發現：Bear 2022 只救 +1.11pp、Bear 2025 反噬 −4.97pp、Combined compound −1.45pp、MDD 改善 0.3pp。整個 85 行規則是負貢獻。
**教訓**：spec 是「已驗證」的產物，不是「等驗證」的草稿。規則設計好但沒實測就寫進 spec = 把未驗證的 bug 裝進 user 的操作手冊。
**Apply**：
- 任何「下個版本加這條規則」的提議，必須同 PR 附上 backtest 證據
- 沿用舊 spec 的規則，若無最近 3 個月內的 backtest → 當作「未驗證」標註、排 backfill task
- 複雜 state machine（cut / reentry / split-guard）比單純 B&H 值得懷疑 — overengineering 是最常見的負貢獻源頭
- 發現無效規則要**刪除**不是「再調參數」；R20 就是範例

---

### 2026-05-13 | 策略的價值不一定在絕對報酬、可能在風險調整後比（R19 G19）
**情境**：R19 算完四市況 compound 發現策略 +33.49% vs 0050 B&H +33.64%（幾乎 tied），乍看「沒 alpha、策略沒用」。但 MDD 只有 −6.85% vs 0050 的 −24.73%（1/4 不到）。風險調整後 return/MDD ratio 4.89 vs 1.36（**好 3.6 倍**）。
**教訓**：「alpha = 0」可以是頂級結果，如果 drawdown 縮到 1/4。只看報酬會得出錯誤結論。
**Apply**：
- 回測報告 headline 必附三個數：絕對報酬 / MDD / return-to-MDD ratio
- 向 user 說 value prop 時先問「你最在意報酬還是回檔」再選對應數字強調
- 「策略勝大盤」語言陷阱要避免；改用「同樣報酬、1/4 drawdown」這種 risk-adjusted framing

---

### 2026-05-13 | 小樣本 annualized Sharpe 是陷阱（R17 G18）
**情境**：R17 算 Layer A v1.2 bull 窗口 annualized Sharpe 2.49，看起來像超強策略。實際上只有 11 筆交易、假設 bull 持續整年才能推到 2.49。真實 per-trade Sharpe 只有 0.51，且 pooled 跨市況 0.32，屬於中等。
**教訓**：Sharpe annualized = Sharpe per-trade × sqrt(trades/year)。小 n 時外推放大倍數不代表真實，是「假設條件延續」的推算。
**Apply**：
- 報告 Sharpe 同時附 per-trade 和 annualized，優先看 per-trade
- 樣本 n < 30 → 標註「信心區間寬、不可單獨作為 go/no-go 依據」
- Pooled 跨市況 Sharpe 比單一市況有參考價值
- 實盤累積 50+ trades 才做 Sharpe 信賴區間評估

---

### 2026-05-12 | 資料 pipeline 必須偵測並調整股票拆分（R15 G17）
**情境**：R15 做 2025 bear 驗證第一輪看到 0050 B&H −67%，明顯不合理。查 raw close 發現 2025-06-18 當日從 $188.65 掉到 $47.57 — 是 1:4 拆分，不是崩盤。Regime engine 把拆分當成熊市、整個 2025-Q3 被誤判為 bear（實際上是 range/bull）。
**教訓**：TWSE STOCK_DAY 等免費 API 回傳 raw close 不做拆分調整。任何用 close 計算 MA / 斜率 / return 的邏輯都會被拆分污染；regime-based portfolio 動作（Layer C 減碼訊號等）會因此發出錯誤指令。
**Apply**：
- Pipeline 啟動時掃所有序列，ratio < 0.5 或 > 2.0 標記 split candidate
- Split-adjust 寫進 data loader、不要在下游每次重算
- 實盤觸發 regime-bear 減碼前，多一層檢查「近 5 日是否發生拆分」
- 除權息（dividend adjustment）是類似但不同的問題，優先級次於 split（影響較小）

---

### 2026-05-12 | Regime confirmed 時放寬規則 > 改 engine / 改門檻（R14 G16）
**情境**：R13 發現 v3 在強 bull 結構性 lag same-universe B&H 49-117pp。R10 已經證明調 regime 門檻（+1~+3）是死區。R14 改走「雙 bull regime 確認時放寬三個旋鈕」（TP1 禁用 / trail 0.70 / 時間停損 60d）→ ALL 24 +20pp 改善、Sharpe 近乎不變、2022 bear 零副作用。
**教訓**：當策略在某 regime lag 時，先問「這 regime 下哪幾個保護機制是在主動拿走報酬」，在該 regime 關掉它們；不要先想重寫 engine 或調門檻。
**Apply**：
- Backtest 顯示某 regime 報酬差 → 列出 strategy 在該 regime 用的每個保護機制（SL、TP、trail、MA 退場、時間停損）
- 找出在該 regime 不必要的 → regime-conditional 關掉
- 其他 regime 保留原規則，對照驗證沒副作用
- 只有 regime 分類本身可疑時才動 engine / 門檻

---

### 2026-05-12 | 「勝過 benchmark」要指定 benchmark 是什麼（R13 G14）
**情境**：R8 宣稱 "Layer B v3 勝 0050 B&H +16pp"。R13 survivorship test 發現 — 用同樣本（scanner 選中的成長股）B&H 對比，v3 **輸 49-117pp**。0050 只是 cap-weighted 大盤代理；若 strategy 有「選股」前置（scanner），真正該打贏的 benchmark 是「相同選股結果 B&H」，否則宣稱的 alpha 其實是 stock-picking alpha 被 strategy rule 吃掉。
**教訓**：Benchmark 要分三層：(1) 大盤 0050/TAIEX（市場 beta）、(2) 同樣本 B&H（stock-picking alpha）、(3) 對照策略（rule alpha）。R8 報告只比 (1)，把 (2)(3) 合在一起當 "strategy alpha" 是誤導。
**Apply**：
- 所有回測報告 MUST 附三層 benchmark
- 若 (2) 遠大於 (1)，要坦誠「alpha 大部分來自 picking、不是 rules」
- Scanner + trade rules 的 case 更要小心：picking 已經做好，rules 若封頂了 upside 就是淨負貢獻

---

### 2026-05-12 | Bull 強度極端時，任何「trade-in/out」設計都會結構性 lag B&H（R13 G15）
**情境**：2025-26 bull 成長股漲 80-270%；v3 的「TP1 +10% 半倉 + trail 20%」數學上封頂單筆 20-30%。結果 v3 在 bull 同樣本比 B&H 少賺 49-117pp，這不是 bug 是設計選擇（用尾部報酬換 drawdown 控制）。
**教訓**：Trade-in/out strategy 的賣點不該是「bull 比 B&H 賺更多」，而是「asymmetric payoff：bull 適度參與、bear 保護」。
**Apply**：
- Bull 報告要坦誠「lag B&H 是設計結果、不是策略失敗」
- Regime confirmed strong bull 時考慮切換到 pure B&H 模式
- 混合策略（bull→B&H / range→v3 / bear→cash）是 R14 方向

---

### 2026-05-09 | 跨 vendor API validation 要用 response fixture 驗、不要複用其他 API 的邏輯（R11 G13）
**情境**：R9 scanner pull 52% 假失敗率讓我誤判「TPEX endpoint 不穩」。R11 診斷：1617/1640 錯誤都來自同一個 bug — 驗證邏輯 `stat == 'OK'` 套用到 TPEX，但 TPEX 回 lowercase `'ok'`，全部被刪檔。
**教訓**：不同 vendor 對 stat/success 欄位的大小寫、命名、結構都可能不同。憑記憶或複製另一個 API 的驗證邏輯 = 地雷。
**未來 apply**：
- 新接 endpoint 先 `curl | jq keys` 確認欄位與值
- 存一筆典型 response 當 fixture，驗證邏輯對著它寫
- 字串比對統一 `.lower() == '...'`，case-insensitive 是唯一安全選擇
- rm 前先 log 原因（避免 bug 把成功檔殺光）

---

### 2026-05-09 | 調參前先做「觀測值分布診斷」（R10 G12）
**情境**：R10 sweep bull 門檻 [+1%, +3%] 得到完全相同結果，事後才發現 2025-26 成長股 MA60 斜率中位數 +28~37%，[+1%, +3%] 區間只佔 < 5% 日子 → 這區間是「死區」。花一小時做 sweep 才發現這件事。
**教訓**：參數 tuning 前若沒先看歷史分布，可能整個 sweep 都在沒意義的區間內打轉。
**未來 apply**：
- 提出「改參數 X」假設前，**先 grep / 統計 X 在樣本中的分布**（median、quartile、百分比落在候選門檻內）
- 若候選值不在觀測區間內 → 不用跑，先換到有意義的值
- 寫 sweep script 時附帶分布診斷（R10 `r10_slope_diag.py` 是範本）

---

## 📦 Archive

> 已歸檔的過時條目
