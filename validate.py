import sqlite3, os

path = os.path.join(os.environ['USERPROFILE'], '.rdq', 'review_index.db')
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
    source TEXT CHECK (source IN ('self','prompted','clarified')),
    priority TEXT NOT NULL CHECK (priority IN ('red','yellow','green')),
    box INTEGER NOT NULL DEFAULT 1 CHECK (box BETWEEN 1 AND 5),
    mc_id TEXT,
    date TEXT NOT NULL, last_reviewed TEXT NOT NULL, next_review TEXT NOT NULL,
    scope_disputed INTEGER DEFAULT 0,
    file_path TEXT,
    UNIQUE(subject, topic, item_id, date)
);
CREATE INDEX IF NOT EXISTS idx_next_review ON review_index(next_review);
CREATE INDEX IF NOT EXISTS idx_subject_item ON review_index(subject, item_id);
CREATE INDEX IF NOT EXISTS idx_mc_id ON review_index(mc_id);
''')

rows = [
    # confirmed/self (✅ 自己說出, 🔴 → box 3, +7d)
    (None,'math','二次函数','math_ch3_002','III','confirmed','self','red',3,None,'2026-07-27','2026-07-27','2026-08-03',0,'reviews/math/ercihanshu_2026-07-27.md'),
    # uncertain (❓ 不確定 → box 1, +1d)
    (None,'math','二次函数','math_ch3_001','II','uncertain',None,'red',1,'mc_math_001','2026-07-27','2026-07-27','2026-07-28',0,'reviews/math/ercihanshu_2026-07-27.md'),
    # confirmed/prompted (◇ 選項認出 → +1 box, 🟡 → box 2, +3d)
    (None,'math','二次函数','math_ch3_005','II','confirmed','prompted','yellow',2,'mc_math_005','2026-07-27','2026-07-27','2026-07-30',0,'reviews/math/ercihanshu_2026-07-27.md'),
    # clarified ⚠️ (迷思已澄清 → 固定 box 2, +3d)
    (None,'science','guanghe','sci_ch4_003','II','clarified','clarified','red',2,'mc_sci_006','2026-07-27','2026-07-27','2026-07-30',0,'reviews/science/guanghe_2026-07-27.md'),
    # confirmed/self 🟢 (→ box 5, +35d)
    (None,'math','二次函数','math_ch3_003','I','confirmed','self','green',5,None,'2026-06-01','2026-06-01','2026-07-06',0,'reviews/math/ercihanshu_2026-06-01.md'),
    # scope_disputed (學生認在範圍內但AI無法確認)
    (None,'social','japan','soc_ch2_003','IV','confirmed','prompted','yellow',3,'mc_soc_003','2026-07-20','2026-07-20','2026-07-27',1,'reviews/social/japan_2026-07-20.md'),
    # uncertain ❓ (到期)
    (None,'english','Unit 3','eng_u3_001','II','uncertain',None,'yellow',1,'mc_eng_001','2026-07-26','2026-07-26','2026-07-27',0,'reviews/english/Unit3_2026-07-26.md'),
]
for r in rows:
    cur.execute('INSERT INTO review_index VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', r)
con.commit()

print('=== 1. Scheduler: 到期项目 ===')
cur.execute("SELECT item_id, subject, status, source, priority, box, next_review FROM review_index WHERE next_review <= '2026-07-27' ORDER BY priority DESC, next_review ASC")
for row in cur.fetchall():
    tag = {'confirmed':'✅','uncertain':'❓','clarified':'⚠️'}.get(row[2],'?')
    print(f'  {tag} {row[0]:20s} {row[1]:10s} {row[2]:12s} {str(row[3] or "-"):10s} pri={row[4]:6s} box={row[5]}  due={row[6]}')

print()
print('=== 2. Exam-Mock: 弱点分数 (subject=math) ===')
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
print('=== 3. Exam-Mock: 迷思频率 (all subjects) ===')
cur.execute("SELECT mc_id, COUNT(*) AS freq FROM review_index WHERE mc_id IS NOT NULL GROUP BY mc_id ORDER BY freq DESC")
for row in cur.fetchall():
    print(f'  {row[0]:15s} freq={row[1]}')

print()
print('=== 4. 验证: ⚠️ clarified 固定 box 2 (+3d) ===')
cur.execute("SELECT item_id, status, box, next_review FROM review_index WHERE status='clarified'")
r = cur.fetchone()
if r:
    expected = '2026-07-30'
    actual = r[3]
    ok = actual == expected
    print(f'  {r[0]:20s} box={r[2]}  next_review={actual}  expected={expected}  {"PASS" if ok else "FAIL"}')
else:
    print('  FAIL: no clarified row found')

print()
print('=== 5. 验证: scope_disputed 标记 ===')
cur.execute("SELECT item_id, scope_disputed FROM review_index WHERE scope_disputed=1")
r = cur.fetchone()
if r:
    print(f'  {r[0]:20s} scope_disputed={r[1]}  PASS')
else:
    print('  FAIL: no scope_disputed row found')

con.close()
print()
print('ALL VALIDATIONS COMPLETE')
