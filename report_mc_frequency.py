"""
RDQ 迷思代碼頻率報表 — 供 Phase 3 判斷哪些 mc_id 需補變體。

用法：
  python report_mc_frequency.py

輸出欄位：
  mc_id        — 迷思代碼
  觸發次數      — 該 mc_id 在 review_index 中出現的總次數
  已探測次數    — MAX(mc_probe_count)，即該 mc_id 被當作迷思探測題問過的最高次數

  ⚠️ 優先       — 觸發次數 ≥ 2，表示已多次出現，有「被記住答案」的風險，應優先補變體
"""

import sqlite3, os

DB_PATH = os.path.join(os.path.expanduser('~'), '.rdq', 'review_index.db')
con = sqlite3.connect(DB_PATH)
cur = con.cursor()

cur.execute("""
    SELECT mc_id, COUNT(*) AS freq, MAX(mc_probe_count) AS max_probes
    FROM review_index
    WHERE mc_id IS NOT NULL
    GROUP BY mc_id
    ORDER BY freq DESC
""")

print(f"{'mc_id':20s} {'觸發次數':10s} {'已探測次數':10s}")
print('-' * 42)
for mc_id, freq, max_probes in cur.fetchall():
    flag = "  ⚠️ 優先" if freq >= 2 else ""
    print(f"{mc_id:20s} {freq:<10d} {max_probes or 0:<10d}{flag}")

con.close()
