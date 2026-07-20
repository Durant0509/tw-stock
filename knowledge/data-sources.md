# 台股資料源清單

> 已實測可用的免費資料源。抓歷史資料前先查這裡，不要重踩坑。
> 更新原則：新發現/失效時 append，標日期與實測結果。

---

## 🥇 Point-in-time 本益比 / 估值（2026-07-16 實測，決定性發現）

### TWSE `BWIBBU_d` — 個股每日本益比、殖利率、股價淨值比

```
https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date=YYYYMMDD&response=json
（舊備援）https://www.twse.com.tw/exchangeReport/BWIBBU_d?response=json&date=YYYYMMDD
```

- **`date=` 回「當天全市場所有股票」**，不是單檔（傳 stockNo 會被忽略）
- 欄位：`證券代號 / 證券名稱 / 收盤價 / 殖利率(%) / 股利年度 / 本益比 / 股價淨值比 / 財報年/季`
- **✅ 本身就是 point-in-time**：`財報年/季` 欄證明 P/E 用「當天已公告」的 EPS 計算
  - 實證：2024-03-15 台積電用「112/4」、味全用「112/3」→ 未公告 Q4 的公司自動 fallback 舊季，**不會用未來資料**
  - 這直接消除 look-ahead bias（playbook R1 鐵則在估值策略裡的生死線）
- **✅ 倖存者偏差天然免疫**：每日快照是「當天實際存在的股票」，後來下市的名字在歷史快照裡都在
- **史料深度**：2022-07-18 抓得到（965 檔在庫），台積電 P/E 19.48 基於「111/1」→ 至少回溯 3 年 OK
- 缺值標記：本益比為「-」代表虧損/無法計算（EPS ≤ 0）

### TWSE `MI_INDEX` type=ALL — 每日收盤行情（含量價 + 本益比一次到位）

```
https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=YYYYMMDD&type=ALL&response=json
```

- 新版回傳 `tables` 陣列（10 個 table），要用 `d['tables'][i]`，不是舊的 `fields1/data1`
- **table[8]「每日收盤行情(全部)」** 是主菜，欄位：
  `證券代號 / 證券名稱 / 成交股數 / 成交筆數 / 成交金額 / 開盤價 / 最高價 / 最低價 / 收盤價 / 漲跌 / 漲跌價差 / … / 本益比`
  - → 一支 API 同時給 **OHLC + 成交量 + 成交金額 + P/E**
  - 成交金額 = 流動性濾網（比張數好，避免低價股假量）
- table[0]「價格指數(TWSE)」= 各**產業別指數**（半導體類/電腦及週邊/光電/電子零組件/航運類/金融保險/鋼鐵…）
  - → 算「熱門族群」動能：產業指數近 20/60 日相對大盤超額報酬

### 產業分類 + 股本 → 市值

```
https://openapi.twse.com.tw/v1/opendata/t187ap03_L   （上市公司基本資料，1089 檔）
```

- 關鍵欄位：`公司代號 / 產業別（代碼，如台積電=24 半導體）/ 已發行普通股數 / 實收資本額 / 上市日期`
- 市值 = 收盤價 × 已發行普通股數
- ⚠️ **caveat**：這是**現在的快照**（出表日 = 抓取當天），股數不是歷史值
  - 影響：歷史「前 150 大」名單有輕微 look-ahead（增減資個股會偏）；大型股 3 年內股本變動小，影響有限
  - 緩解：rebalance 用「當時價 × 現股數」動態排名；要嚴謹再補歷史股本（工程量中等）

---

## 抓取成本 / 注意事項

- 3 年 ≈ 720 交易日；`MI_INDEX` + `BWIBBU_d` 各一次 = ~1,440 requests，一次性 ~30–60 分鐘
- **落地快取到 disk**，回測不再打 API
- 禮貌速率：≥ 1 req/sec + 遇 429/空回應 backoff（沿用 playbook R11「rm 前先 log 原因」精神，別把成功檔誤刪）
- 驗證邏輯用 `stat.lower() == 'ok'`（playbook R11 G13：TPEX 回小寫 `ok` 曾害假失敗）

---

## 舊有紀錄（playbook 已載，摘要備查）

- 即時報價：`mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_XXXX.tw`
- 日線 OHLC：`twse.com.tw/rwd/zh/afterTrading/STOCK_DAY`
- 加權指數長歷史代理：`STOCK_DAY stockNo=0050`（tracking error ~2-3%）
- 個股綜合面（P/E、頭條）人看：`tw.stock.yahoo.com/quote/XXXX.TW`
- **不要先試** Goodinfo / MOPS `t05st10_ifrs`（常空回或被擋）
