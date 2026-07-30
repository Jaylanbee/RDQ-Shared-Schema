## RDQ 系統操作流程

### 學生複習（RDQ-Learn-Student）

```
使用者說「幫我複習 OOO」

  → [早退分支] 若使用者說「我只想問一題」「直接幫我解」
    → 跳過整套七階段，直接走一般教學模式回答

  → Phase 0: 判定科目/範圍/模式 (Lite/Full)
    若科目不明確 → 確認後再進 Phase 1

  → Phase 1: 引導回憶（L1 開放式）

  → Phase 2: 解惑（反問→L2 選項）

  → Phase 2.5: 學生自發列舉（不插話→挑一題挖）

  → Phase 3: 隱性知識挖掘
    從 question-bank.md 選起始問句
    若 mc_id 有多個變體 → 查 review_index 最近一筆 mc_probe_variant，排除該變體

  → Phase 4: 盲點提示（Full 模式）

  → Phase 5: 產出覆盤卡（spec-template.md 模板）

  → Phase 6: 學生確認

  → Phase 7: 寫回
    1. 對每個 item 呼叫 leitner.next_box() 算新 box 與 next_review
2. INSERT 到 ~/.education_ecosystem/review_index.db（append-only，不 UPDATE）
3. 寫覆盤卡至 ~/.education_ecosystem/reviews/{subject}/{slug}_{date}.md
    若觸發迷思探測 → 記錄 mc_probe_variant
```

### 每日提醒（RDQ-Scheduler）

```
Windows Task Scheduler 每日 17:00（純自動化，無 LLM）
  → scheduler.ps1 觸發
  → scheduler.py 執行 query_due()：

     SELECT item_id, subject, topic, status, source, priority, box, mc_id, file_path
     FROM review_index
     WHERE next_review <= ?
     ORDER BY CASE priority WHEN 'red' THEN 0 WHEN 'yellow' THEN 1 WHEN 'green' THEN 2 END,
              next_review ASC
     （完整清單，無 LIMIT；priority 用 CASE 確保 🔴 排最前，不以字母排序）

  → 寫入 ~/.rdq/last_reminder.txt（結構化原始文字，唯讀不回寫）
    三種結果：空清單 / 有到期項目 / 例外

  → 學生或家長之後主動詢問 AI（模式 A）時，才由 LLM 語氣層溫和呈現，一次一項
```

### 段考後維運（Phase 3）

```
1. python report_mc_frequency.py
   → 輸出 mc_id 觸發次數降冪，freq≥2 標 ⚠️ 優先
2. 挑前 5 個 ⚠️ mc_id
3. 補寫 variant b/c（不同情境/數字，同一底層迷思）
4. 人工審核（驗算、歸類、敏感度、變體歧異度）
5. commit → push
```

### 健檢（開發者）

```
python validate.py
  → 獨立測試庫 review_index_test.db（不碰真實 ~/.rdq/review_index.db）
  → 8 項驗證（schema、到期查詢、弱點分數、leitner 跳箱、scope、mc_probe_variant 輪替邏輯）
  → 全部 PASS 才算通過
```
