# RDQ Shared Schema — 跨 Agent 資料契約

> 發行者：RDQ-Learn-Student   消費端：RDQ-Scheduler, RDQ-Exam-Mock
> 版本：1.3
> 更新日：2026-07-28

## 核心原則

1. **SQLite 是唯一事實來源**（執行期狀態，不進 git）
2. **Markdown 覆盤卡是展示層**（給人讀的，agent 之間不直接解析）
3. **單向流**：RDQ → SQLite（寫入），SQLite → Scheduler / Exam-Mock（讀取）
4. **資料夾隔離**：原始碼（SKILL.md, question-bank.md）在 git 中版控；`review_index.db` 在本機 `~/.rdq/` 下，不進 git

---

## 資料庫結構

資料庫路徑慣例：`~/.rdq/review_index.db`（無關各 repo 的 Git 工作目錄）

### Table: `review_index`

```sql
CREATE TABLE review_index (
    -- 主鍵
    id            INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 識別欄位
    subject       TEXT    NOT NULL,  -- math | science | chinese | english | social
    topic         TEXT    NOT NULL,  -- 單元名稱，如 "二次函數"、"光合作用"
    item_id       TEXT    NOT NULL,  -- 知識點代碼，如 "math_ch3_002"
    quadrant      TEXT,              -- I | II | III | IV  可為 NULL（未分類）

    -- 狀態欄位（由 RDQ 判定）
    status        TEXT    NOT NULL CHECK (status IN ('confirmed', 'uncertain', 'clarified')),
    source        TEXT    CHECK (source IN ('self', 'prompted')),
    --  self      = ✅ 自己說出來
    --  prompted  = ✅ 選項認出來
    --  NULL      = ❓ uncertain 或 ⚠️ clarified（排程只讀 status，不讀 source）
    --  ⚠️ 迷思已澄清的 Leitner：固定 box 2（+3 天），不受 priority 影響

    -- 用於 Leitner 排程
    priority      TEXT    NOT NULL CHECK (priority IN ('red', 'yellow', 'green')),
    box           INTEGER NOT NULL DEFAULT 1 CHECK (box BETWEEN 1 AND 5),

    -- 用於診斷
    mc_id         TEXT,              -- 迷思代碼，如 "mc_math_002"；NULL = 無對應迷思
    mc_probe_count INTEGER DEFAULT 0, -- 此 mc_id 被當作迷思探測題問過的次數（防題目老化）
    mc_probe_variant TEXT,             -- 該次使用的迷思探測題變體代號，如 'a'/'b'；NULL = 未觸發迷思探測

    -- 日期時間
    date          TEXT    NOT NULL,  -- 覆盤日期 ISO 8601
    last_reviewed TEXT    NOT NULL,  -- 同 date（保留欄位以便未來更新同一 item）
    next_review   TEXT    NOT NULL,  -- 下次複習日期 ISO 8601

    -- 範圍爭議
    scope_disputed INTEGER DEFAULT 0,  -- 0=無爭議，1=學生認為在範圍內但AI無法確認
    scope_confirmed INTEGER DEFAULT 0,  -- 0=未確認，1=範圍爭議經L1確認後學生答對

    -- 檔案路徑
    file_path     TEXT,              -- reviews/{subject}/{topic_slug}_{date}.md 相對路徑

    -- 唯一約束：同一知識點同一天不重複記錄
    UNIQUE(subject, topic, item_id, date)
);

CREATE INDEX idx_next_review ON review_index(next_review);
CREATE INDEX idx_subject_item ON review_index(subject, item_id);
CREATE INDEX idx_mc_id ON review_index(mc_id);
```

### Leitner Box 參數

實作位於 `leitner.py`，由 RDQ-Learn-Student Phase 7 寫入時呼叫。
Scheduler 只讀已算好的 box/next_review，不執行跳箱計算。

| Box | 間隔（天） | 🔴 上限 | 跳箱規則 |
|-----|-----------|---------|---------|
| 1   | 1         | 無限制   | 起點    |
| 2   | 3         | 無限制   | ◇ 過關 → 跳 1 箱；✓ → 跳 2 箱 |
| 3   | 7         | 🔴 上限  | ✓ 過關但 🔴 鎖在此箱 |
| 4   | 16        | 🔴 不可達 | 僅 🟡🟢 可達 |
| 5   | 35        | 🔴 不可達 | 僅 🟡🟢 可達 |

- ❓（status='uncertain'）→ 無論目前在哪一箱，**直接回 box 1**
- ✓（source='self'）→ 跳 +2 箱（上限 box 5），🔴 鎖在 box 3 不超過
- ◇（source='prompted'）→ 跳 +1 箱（上限 box 5），🔴 鎖在 box 3 不超過
- ⚠️（status='clarified'）→ **固定 box 2（+3 天）**，不受 priority 或原本 box 影響。迷思復發率高，需比普通 ❓ 更快回訪驗證。source=null（排程只讀 status）

---

## 消費端查詢 Pseudocode

### RDQ-Scheduler — 今天到期的項目

```
-- 輸入：today = "2026-07-27", subject = "math"（可選）
-- 輸出：到期 item 清單

SELECT item_id, subject, topic, status, source, priority, box, mc_id
FROM review_index
WHERE next_review <= today
  AND subject = ?           -- 若指定科目
ORDER BY priority DESC, next_review ASC
LIMIT 10;
```

Scheduler 收到結果後：
1. 依 `priority` 排序（🔴 優先 🟡 次之 🟢 最後）
2. 用 LLM 包裝成溫和語氣：`「你上次複習的 math_ch3_002 到期了，要現在看一下嗎？」`
3. 注意：Scheduler 的 LLM **只做語氣層**，不做任何判斷。判斷全部由 SQL 完成。

### RDQ-Exam-Mock — 弱點加權抽樣

```
-- 輸入：today, subject
-- 輸出：依弱點分數 × 命題權重排序的抽樣候選清單

-- 第一步：計算每個知識點的「弱點分數」
-- 分數公式 = 1（uncertain） + 0.3（source='prompted'） + 0.5（近期 ❓ 次數）
-- 近期：過去 30 天

WITH weakness AS (
    SELECT
        item_id,
        subject,
        MAX(CASE WHEN status = 'uncertain' THEN 1.0 ELSE 0 END) +
        MAX(CASE WHEN source = 'prompted' THEN 0.3 ELSE 0 END) +
        COUNT(CASE WHEN status = 'uncertain'
                    AND date >= DATE('now', '-30 days') THEN 1 END) * 0.5
        AS weakness_score,
        COUNT(*) AS total_reviews,
        COUNT(CASE WHEN status = 'uncertain' THEN 1 END) AS uncertain_count
    FROM review_index
    WHERE subject = ?
    GROUP BY item_id
),
-- 第二步：依迷思代碼做頻率聚合（用於診斷報表）
misconception_stats AS (
    SELECT
        mc_id,
        COUNT(*) AS frequency,
        COUNT(DISTINCT item_id) AS affected_items
    FROM review_index
    WHERE subject = ?
      AND mc_id IS NOT NULL
      AND date >= DATE('now', '-90 days')
    GROUP BY mc_id
    ORDER BY frequency DESC
)
-- 第三步：結合命題權重（命題權重表另由 Exam-Mock 維護）
SELECT
    w.item_id,
    w.subject,
    w.weakness_score,
    w.uncertain_count,
    COALESCE(e.exam_weight, 0.1) AS exam_weight,
    w.weakness_score * COALESCE(e.exam_weight, 0.1) AS selection_score
FROM weakness w
LEFT JOIN exam_weights e ON w.item_id = e.item_id
ORDER BY selection_score DESC;
```

Exam-Mock 收到結果後：
1. 依 `selection_score` 取前 N 題（依段考範圍長度決定）
2. 用 LLM 包裝成會考風格情境題
3. 延續 RDQ 的 L1→L2 鷹架哲學（先問→選項接住）
4. **但加入明確對錯回饋**（與 RDQ 不同——模擬考需要告訴學生正確答案）

### 輔助 Table（Exam-Mock 自用）

```sql
CREATE TABLE exam_weights (
    item_id     TEXT PRIMARY KEY,  -- 同 review_index.item_id
    subject     TEXT NOT NULL,
    exam_weight REAL NOT NULL DEFAULT 0.1 CHECK (exam_weight BETWEEN 0 AND 1),
    -- 會考命題權重，來源：歷屆會考題目統計
    last_updated TEXT NOT NULL
);
```

`exam_weights` 由 Exam-Mock 維護，RDQ 與 Scheduler 不讀寫此表。

---

## 驗證流程

寫入與讀取的完整循環驗證步驟：

```
1. RDQ Phase 7 寫入完成後，檢查 SQLite：
   sqlite> SELECT COUNT(*) FROM review_index WHERE date = '2026-07-27';

2. Scheduler 查詢：
   sqlite> SELECT item_id, next_review FROM review_index
           WHERE next_review <= '2026-07-28';

3. 驗證 Leitner 跳箱邏輯：
   寫入一筆 status='confirmed', source='self', priority='green', box=1
   → 期望 box → 3, next_review → +7 天

   寫入一筆 status='uncertain', priority='red', box=4
   → 期望 box → 1, next_review → +1 天

4. Exam-Mock 弱點聚合（手動插入 5 筆假資料驗證）：
   sqlite> SELECT COUNT(*) FROM review_index WHERE subject='math';
```

---

## 不在此契約範圍內

- `exam_weights` 表結構與維護方式（Exam-Mock 自行負責）
- 覆盤卡片 markdown 模板（屬於 RDQ-Learn-Student 展示層）
- SQLite 的備份與清理策略（使用者自行管理）

---

## 版本紀錄

| 版本 | 日期 | 變更 |
|-----|------|------|
| 1.0 | 2026-07-27 | 初始契約定義 |
| 1.1 | 2026-07-27 | status 兩態→三態（+clarified），source 收回（self|prompted），加 scope_disputed / scope_confirmed / mc_probe_count |
| 1.2 | 2026-07-27 | source 收回（移除 clarified 枚舉），加 scope_confirmed, mc_probe_count 欄位，刪外層 priority/next_review_date/mode_used |
| 1.3 | 2026-07-28 | 新增 mc_probe_variant（記錄該次使用的迷思探測題變體，供選題邏輯查詢歷史避免重複） |
