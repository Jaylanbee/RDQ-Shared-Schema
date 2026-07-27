-- RDQ Shared Schema — 驗證用假資料（手動 10 筆）
-- 用法：sqlite3 ~/.rdq/review_index.db < validate.sql

-- 建立表
CREATE TABLE IF NOT EXISTS review_index (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    subject       TEXT    NOT NULL,
    topic         TEXT    NOT NULL,
    item_id       TEXT    NOT NULL,
    quadrant      TEXT,
    status        TEXT    NOT NULL CHECK (status IN ('confirmed', 'uncertain')),
    source        TEXT    CHECK (source IN ('self', 'prompted')),
    priority      TEXT    NOT NULL CHECK (priority IN ('red', 'yellow', 'green')),
    box           INTEGER NOT NULL DEFAULT 1 CHECK (box BETWEEN 1 AND 5),
    mc_id         TEXT,
    date          TEXT    NOT NULL,
    last_reviewed TEXT    NOT NULL,
    next_review   TEXT    NOT NULL,
    file_path     TEXT,
    UNIQUE(subject, topic, item_id, date)
);

CREATE INDEX IF NOT EXISTS idx_next_review ON review_index(next_review);
CREATE INDEX IF NOT EXISTS idx_subject_item ON review_index(subject, item_id);
CREATE INDEX IF NOT EXISTS idx_mc_id ON review_index(mc_id);

-- 清空舊資料（測試用）
DELETE FROM review_index;

-- 插入 10 筆假資料（today = 2026-07-27）
INSERT INTO review_index VALUES
-- 1. 到期的基本概念 🔴
(NULL, 'math', '二次函數', 'math_ch3_002', 'III', 'confirmed', 'prompted', 'red', 2, 'mc_math_002', '2026-07-24', '2026-07-24', '2026-07-27', 'reviews/math/二次函數_2026-07-24.md'),
-- 2. 已到期的待確認 ❓
(NULL, 'math', '二次函數', 'math_ch3_001', 'II', 'uncertain', NULL, 'red', 1, 'mc_math_001', '2026-07-26', '2026-07-26', '2026-07-27', 'reviews/math/二次函數_2026-07-26.md'),
-- 3. 尚未到期（明天）
(NULL, 'math', '二次函數', 'math_ch3_005', 'II', 'uncertain', NULL, 'yellow', 1, 'mc_math_005', '2026-07-27', '2026-07-27', '2026-07-28', 'reviews/math/二次函數_2026-07-27.md'),
-- 4. 已經很熟的 🟢 box 5
(NULL, 'math', '二次函數', 'math_ch3_003', 'I', 'confirmed', 'self', 'green', 5, NULL, '2026-06-01', '2026-06-01', '2026-07-06', 'reviews/math/二次函數_2026-06-01.md'),
-- 5. 自然到期 ✅
(NULL, 'science', '光合作用', 'sci_ch4_001', 'I', 'confirmed', 'self', 'green', 4, NULL, '2026-07-10', '2026-07-10', '2026-07-26', 'reviews/science/光合作用_2026-07-10.md'),
-- 6. 自然到期 🔴
(NULL, 'science', '光合作用', 'sci_ch4_002', 'III', 'confirmed', 'prompted', 'red', 2, 'mc_sci_001', '2026-07-24', '2026-07-24', '2026-07-27', 'reviews/science/光合作用_2026-07-24.md'),
-- 7. 英文到期 ❓
(NULL, 'english', 'Unit 3', 'eng_u3_001', 'II', 'uncertain', NULL, 'yellow', 1, 'mc_eng_001', '2026-07-26', '2026-07-26', '2026-07-27', 'reviews/english/Unit-3_2026-07-26.md'),
-- 8. 社會到期 ✅
(NULL, 'social', '日治時期', 'soc_ch2_003', 'IV', 'confirmed', 'prompted', 'yellow', 3, 'mc_soc_003', '2026-07-20', '2026-07-20', '2026-07-27', 'reviews/social/日治時期_2026-07-20.md'),
-- 9. 國文到期 ✅（🔴 鎖 box 3）
(NULL, 'chinese',岳陽樓記', 'chi_l3_001', 'I', 'confirmed', 'self', 'red', 3, NULL, '2026-07-20', '2026-07-20', '2026-07-27', 'reviews/chinese/岳陽樓記_2026-07-20.md'),
-- 10. 過去 30 天內多次 ❓（模擬弱點）
(NULL, 'math', '二次函數', 'math_ch3_004', 'II', 'uncertain', NULL, 'red', 1, 'mc_math_004', '2026-07-01', '2026-07-01', '2026-07-02', 'reviews/math/二次函數_2026-07-01.md');
-- 再加一筆同一 item_id 最近又 ❓（模擬重複弱點）
INSERT INTO review_index VALUES
(NULL, 'math', '二次函數', 'math_ch3_004', 'II', 'uncertain', NULL, 'red', 1, 'mc_math_004', '2026-07-15', '2026-07-15', '2026-07-16', 'reviews/math/二次函數_2026-07-15.md');

-- === 驗證查詢 1：Scheduler 今天到期 ===
.print '=== Scheduler: 到期項目 ==='
SELECT item_id, subject, priority, box, next_review
FROM review_index
WHERE next_review <= '2026-07-27'
ORDER BY priority DESC, next_review ASC;

-- === 驗證查詢 2：Exam-Mock 弱點分數 ===
.print ''
.print '=== Exam-Mock: 弱點分數 ==='
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
    WHERE subject = 'math'
    GROUP BY item_id
)
SELECT * FROM weakness ORDER BY weakness_score DESC;

-- === 驗證查詢 3：迷思頻率 ===
.print ''
.print '=== Exam-Mock: 迷思頻率 (subject=math) ==='
SELECT mc_id, COUNT(*) AS frequency
FROM review_index
WHERE subject = 'math'
  AND mc_id IS NOT NULL
GROUP BY mc_id
ORDER BY frequency DESC;
