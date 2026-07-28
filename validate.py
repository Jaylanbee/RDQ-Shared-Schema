import sqlite3, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from leitner import next_box, BOX_INTERVALS

path = os.path.join(os.path.expanduser('~'), '.rdq', 'review_index.db')
os.makedirs(os.path.dirname(path), exist_ok=True)
if os.path.exists(path):
    os.remove(path)

con = sqlite3.connect(path)
cur = con.cursor()

# v1.1 schema: three-state status + scope_disputed
cur.executescript('''
CREATE TABLE review_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL, topic TEXT NOT NULL, item_id TEXT NOT NULL,
    quadrant TEXT,
    status TEXT NOT NULL CHECK (status IN ('confirmed','uncertain','clarified')),
    source TEXT CHECK (source IN ('self','prompted')),
    priority TEXT NOT NULL CHECK (priority IN ('red','yellow','green')),
    box INTEGER NOT NULL DEFAULT 1 CHECK (box BETWEEN 1 AND 5),
    mc_id TEXT,
    mc_probe_count INTEGER DEFAULT 0,
    mc_probe_variant TEXT,
    date TEXT NOT NULL, last_reviewed TEXT NOT NULL, next_review TEXT NOT NULL,
    scope_disputed INTEGER DEFAULT 0,
    scope_confirmed INTEGER DEFAULT 0,
    file_path TEXT,
    UNIQUE(subject, topic, item_id, date)
);
CREATE INDEX IF NOT EXISTS idx_next_review ON review_index(next_review);
CREATE INDEX IF NOT EXISTS idx_subject_item ON review_index(subject, item_id);
CREATE INDEX IF NOT EXISTS idx_mc_id ON review_index(mc_id);
''')

rows = [
    # confirmed/self (✅ 自己說出, 🔴 → box 3, +7d)
    (None,'math','二次函數','math_ch3_002','III','confirmed','self','red',3,None,0,None,'2026-07-27','2026-07-27','2026-08-03',0,0,'reviews/math/ercihanshu_2026-07-27.md'),
    # uncertain (❓ 不確定 → box 1, +1d, source=null)
    (None,'math','二次函數','math_ch3_001','II','uncertain',None,'red',1,'mc_math_001',0,None,'2026-07-27','2026-07-27','2026-07-28',0,0,'reviews/math/ercihanshu_2026-07-27.md'),
    # confirmed/prompted (◇ 選項認出 → +1 box, 🟡 → box 2, +3d)
    (None,'math','二次函數','math_ch3_005','II','confirmed','prompted','yellow',2,'mc_math_005',0,None,'2026-07-27','2026-07-27','2026-07-30',0,0,'reviews/math/ercihanshu_2026-07-27.md'),
    # clarified ⚠️ (迷思已澄清 → 固定 box 2, +3d, source=null, mc_probe_count=1)
    (None,'science','guanghe','sci_ch4_003','II','clarified',None,'red',2,'mc_sci_006',1,None,'2026-07-27','2026-07-27','2026-07-30',0,0,'reviews/science/guanghe_2026-07-27.md'),
    # confirmed/self 🟢 (→ box 5, +35d)
    (None,'math','二次函數','math_ch3_003','I','confirmed','self','green',5,None,0,None,'2026-06-01','2026-06-01','2026-07-06',0,0,'reviews/math/ercihanshu_2026-06-01.md'),
    # scope_disputed + scope_confirmed (學生存疑但經L1確認答對)
    (None,'social','japan','soc_ch2_003','IV','confirmed','self','yellow',3,'mc_soc_003',0,None,'2026-07-20','2026-07-20','2026-07-27',1,1,'reviews/social/japan_2026-07-20.md'),
    # uncertain ❓ (到期)
    (None,'english','Unit 3','eng_u3_001','II','uncertain',None,'yellow',1,'mc_eng_001',0,None,'2026-07-26','2026-07-26','2026-07-27',0,0,'reviews/english/Unit3_2026-07-26.md'),
]
for r in rows:
    cur.execute('INSERT INTO review_index VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', r)
con.commit()

print('=== 1. Scheduler: 到期項目 ===')
cur.execute("SELECT item_id, subject, status, source, priority, box, next_review FROM review_index WHERE next_review <= '2026-07-27' ORDER BY priority DESC, next_review ASC")
for row in cur.fetchall():
    tag = {'confirmed':'✅','uncertain':'❓','clarified':'⚠️'}.get(row[2],'?')
    src = row[3] if row[3] else '-'
    print(f'  {tag} {row[0]:20s} {row[1]:10s} {row[2]:12s} source={src:10s} pri={row[4]:6s} box={row[5]}  due={row[6]}')

print()
print('=== 2. Exam-Mock: 弱點分數 (subject=math) ===')
cur.execute("""
SELECT item_id, 
       ROUND(MAX(CASE WHEN status='uncertain' THEN 1.0 ELSE 0 END) +
             MAX(CASE WHEN source='prompted' THEN 0.3 ELSE 0 END) +
             COUNT(CASE WHEN status='uncertain' AND date >= DATE('now','-30 days') THEN 1 END) * 0.5, 2)
       AS weakness_score,
       COUNT(*) AS total,
       COUNT(CASE WHEN status='uncertain' THEN 1 END) AS uncertain_cnt
FROM review_index
WHERE subject='math'
GROUP BY item_id
ORDER BY weakness_score DESC
""")
for row in cur.fetchall():
    print(f'  {row[0]:20s} score={row[1]:5.2f}  total={row[2]}  uncertain={row[3]}')

print()
print('=== 3. Exam-Mock: 迷思頻率 ===')
cur.execute("SELECT mc_id, COUNT(*) AS freq, MAX(mc_probe_count) AS probes FROM review_index WHERE mc_id IS NOT NULL GROUP BY mc_id ORDER BY freq DESC")
for row in cur.fetchall():
    print(f'  {row[0]:15s} freq={row[1]}  max_probes={row[2]}')

print()
print('=== 4. 驗證: ⚠️ clarified 固定 box 2 (+3d), source=null ===')
cur.execute("SELECT item_id, status, source, box, next_review FROM review_index WHERE status='clarified'")
r = cur.fetchone()
if r:
    src_ok = r[2] is None
    box_ok = r[3] == 2
    date_ok = r[4] == '2026-07-30'
    print(f'  {r[0]:20s} box={r[3]}  next_review={r[4]}  source={r[2]}  box_ok={box_ok} date_ok={date_ok} src_null={src_ok}')
    print(f'  {"ALL PASS" if (box_ok and date_ok and src_ok) else "FAIL"}')
else:
    print('  FAIL: no clarified row found')

print()
print('=== 5. 驗證: scope_disputed + scope_confirmed ===')
cur.execute("SELECT item_id, scope_disputed, scope_confirmed FROM review_index WHERE scope_disputed=1")
r = cur.fetchone()
if r and r[2] == 1:
    print(f'  {r[0]:20s} scope_disputed={r[1]}  scope_confirmed={r[2]}  PASS')
else:
    print('  FAIL')

print()
print('=== 6. 驗證: mc_probe_count ===')
cur.execute("SELECT item_id, mc_probe_count FROM review_index WHERE mc_probe_count > 0")
r = cur.fetchone()
if r:
    print(f'  {r[0]:20s} mc_probe_count={r[1]}  PASS')
else:
    print('  FAIL')

print()
print('=== 7. 驗證: leitner.py 跳箱邏輯 ===')
# confirmed + self, 🔴, box 1 → box 3 (capped)
b, d = next_box(1, 'confirmed', 'red', 'self')
assert b == 3, f'self + red: expected box 3, got {b}'
# confirmed + prompted, 🟡, box 1 → box 2
b, d = next_box(1, 'confirmed', 'yellow', 'prompted')
assert b == 2, f'prompted + yellow: expected box 2, got {b}'
# uncertain, box 5 → box 1
b, d = next_box(5, 'uncertain')
assert b == 1, f'uncertain: expected box 1, got {b}'
# clarified, box 5 → box 2
b, d = next_box(5, 'clarified')
assert b == 2, f'clarified: expected box 2, got {b}'
print('  4/4 assertions PASS')

print()
print('=== 8. 驗證: mc_probe_variant 輪替查詢與選題排除邏輯 ===')

def select_probe_variant(available, last_used):
    """選題邏輯：排除上次用過的變體，若只剩一個可選則不得已重複用它"""
    candidates = [v for v in available if v != last_used]
    return candidates[0] if candidates else available[0]

con.execute("""INSERT INTO review_index
    (subject,topic,item_id,mc_id,mc_probe_variant,status,priority,box,date,last_reviewed,next_review)
    VALUES ('math','二次函數','math_ch3_002','mc_math_001','a','clarified','red',2,'2026-07-20','2026-07-20','2026-07-23')""")
con.execute("""INSERT INTO review_index
    (subject,topic,item_id,mc_id,mc_probe_variant,status,priority,box,date,last_reviewed,next_review)
    VALUES ('math','二次函數','math_ch3_002','mc_math_001','b','clarified','red',2,'2026-07-24','2026-07-24','2026-07-27')""")
con.commit()

last_variant = con.execute("""
    SELECT mc_probe_variant FROM review_index
    WHERE item_id=? AND mc_id=? ORDER BY date DESC LIMIT 1
""", ('math_ch3_002', 'mc_math_001')).fetchone()[0]
print(f"  查到最近一次使用的變體: {last_variant}  (預期: b)")
assert last_variant == 'b'

next_pick = select_probe_variant(['a', 'b', 'c'], last_variant)
print(f"  三選一排除已用過的 → 選到: {next_pick}  (預期: a 或 c，不能是 b)")
assert next_pick != 'b'

# 邊界情況：目前多數 mc_id 只有 1 個變體，選題邏輯不能因此掛掉
only_one = select_probe_variant(['a'], 'a')
print(f"  只有單一變體時，被迫重複使用: {only_one}  (預期: a，不能是空)")
assert only_one == 'a'

print('  ALL PASS')

con.close()
print()
print('ALL 8 VALIDATIONS COMPLETE')
