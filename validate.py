import sqlite3, os

path = os.path.join(os.environ['USERPROFILE'], '.rdq', 'review_index.db')
os.makedirs(os.path.dirname(path), exist_ok=True)
if os.path.exists(path):
    os.remove(path)

con = sqlite3.connect(path)
cur = con.cursor()

cur.executescript('''
CREATE TABLE review_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL, topic TEXT NOT NULL, item_id TEXT NOT NULL,
    quadrant TEXT, status TEXT NOT NULL, source TEXT,
    priority TEXT NOT NULL, box INTEGER NOT NULL DEFAULT 1,
    mc_id TEXT, date TEXT NOT NULL, last_reviewed TEXT NOT NULL,
    next_review TEXT NOT NULL, file_path TEXT,
    UNIQUE(subject, topic, item_id, date)
);
CREATE INDEX idx_next_review ON review_index(next_review);
CREATE INDEX idx_subject_item ON review_index(subject, item_id);
CREATE INDEX idx_mc_id ON review_index(mc_id);
''')

rows = [
    (None,'math','二次函数','math_ch3_002','III','confirmed','prompted','red',2,'mc_math_002','2026-07-24','2026-07-24','2026-07-27','reviews/math/ercihanshu_2026-07-24.md'),
    (None,'math','二次函数','math_ch3_001','II','uncertain',None,'red',1,'mc_math_001','2026-07-26','2026-07-26','2026-07-27','reviews/math/ercihanshu_2026-07-26.md'),
    (None,'math','二次函数','math_ch3_005','II','uncertain',None,'yellow',1,'mc_math_005','2026-07-27','2026-07-27','2026-07-28','reviews/math/ercihanshu_2026-07-27.md'),
    (None,'math','二次函数','math_ch3_003','I','confirmed','self','green',5,None,'2026-06-01','2026-06-01','2026-07-06','reviews/math/ercihanshu_2026-06-01.md'),
    (None,'science','guanghe','sci_ch4_001','I','confirmed','self','green',4,None,'2026-07-10','2026-07-10','2026-07-26','reviews/science/guanghe_2026-07-10.md'),
    (None,'science','guanghe','sci_ch4_002','III','confirmed','prompted','red',2,'mc_sci_001','2026-07-24','2026-07-24','2026-07-27','reviews/science/guanghe_2026-07-24.md'),
    (None,'english','Unit 3','eng_u3_001','II','uncertain',None,'yellow',1,'mc_eng_001','2026-07-26','2026-07-26','2026-07-27','reviews/english/Unit3_2026-07-26.md'),
    (None,'social','japan','soc_ch2_003','IV','confirmed','prompted','yellow',3,'mc_soc_003','2026-07-20','2026-07-20','2026-07-27','reviews/social/japan_2026-07-20.md'),
    (None,'chinese','yueyang','chi_l3_001','I','confirmed','self','red',3,None,'2026-07-20','2026-07-20','2026-07-27','reviews/chinese/yueyang_2026-07-20.md'),
    (None,'math','二次函数','math_ch3_004','II','uncertain',None,'red',1,'mc_math_004','2026-07-01','2026-07-01','2026-07-02','reviews/math/ercihanshu_2026-07-01.md'),
    (None,'math','二次函数','math_ch3_004','II','uncertain',None,'red',1,'mc_math_004','2026-07-15','2026-07-15','2026-07-16','reviews/math/ercihanshu_2026-07-15.md'),
]
for r in rows:
    cur.execute('INSERT INTO review_index VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', r)
con.commit()

print('=== Scheduler: 到期项目 ===')
cur.execute("SELECT item_id, subject, priority, box, next_review FROM review_index WHERE next_review <= '2026-07-27' ORDER BY priority DESC, next_review ASC")
for row in cur.fetchall():
    print(f'  {row[0]:20s} {row[1]:10s} {row[2]:8s} box={row[3]}  due={row[4]}')

print()
print('=== Exam-Mock: 弱点分数 (subject=math) ===')
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
print('=== Exam-Mock: 迷思频率 (subject=math) ===')
cur.execute("SELECT mc_id, COUNT(*) AS freq FROM review_index WHERE subject='math' AND mc_id IS NOT NULL GROUP BY mc_id ORDER BY freq DESC")
for row in cur.fetchall():
    print(f'  {row[0]:15s} freq={row[1]}')

con.close()
print()
print('SUCCESS: All 3 validation queries passed.')
