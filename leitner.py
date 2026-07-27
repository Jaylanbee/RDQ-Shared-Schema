"""
RDQ Shared Leitner Logic — 唯一權威實作。

所有 repo 中關於 Leitner 跳箱的計算只應在此處定義。
RDQ-Learn-Student (Phase 7 寫入時呼叫) 與 RDQ-Scheduler (讀取參考) 皆 import 此模組。

用法：
  from leitner import next_box, next_review_date, BOX_INTERVALS

  引入　Box 規則　(new_box, new_review) = next_box(current_box, status, priority, source)
"""

from datetime import date, timedelta

# ── Box 間隔（天） ──────────────────────────────────────
BOX_INTERVALS = {1: 1, 2: 3, 3: 7, 4: 16, 5: 35}
MAX_BOX = 5
RED_CAP = 3  # 🔴 priority items 上限 box 3


def next_box(current_box: int, status: str, priority: str = "green",
             source: str = None) -> tuple:
    """
    根據目前 box、status、priority、source 計算新 box 與 next_review 日期。

    參數：
      current_box : 該 item 最近一筆記錄的 box（1-5）
      status      : confirmed | uncertain | clarified
      priority    : red | yellow | green（僅 confirmed 時生效）
      source      : self | prompted（僅 confirmed 時需要；= ✅ 怎麼確認的）

    回傳：
      (new_box: int, next_review: str)  # next_review 為 ISO 日期字串

    規則摘要：
      - uncertain  → box 1（重置）
      - clarified  → box 2（固定，迷思復發率高）
      - confirmed + self     → +2 box（🔴 上限 box 3）
      - confirmed + prompted → +1 box（🔴 上限 box 3）
    """
    today = date.today()

    if status == "uncertain":
        new_box = 1

    elif status == "clarified":
        new_box = 2  # 固定 box 2，不受 priority 或原本 box 影響

    elif status == "confirmed":
        if source == "self":
            new_box = current_box + 2
        elif source == "prompted":
            new_box = current_box + 1
        else:
            raise ValueError(f"confirmed 狀態需要有效的 source，收到: {source}")

        # 上限 box 5
        new_box = min(new_box, MAX_BOX)

        # 🔴 鎖在 box 3
        if priority == "red":
            new_box = min(new_box, RED_CAP)

    else:
        raise ValueError(f"未知 status: {status}")

    interval = BOX_INTERVALS.get(new_box, 1)
    next_review = (today + timedelta(days=interval)).isoformat()

    return new_box, next_review


def next_review_date(box: int) -> str:
    """給定 box，回傳下次複習日期（ISO 字串）。"""
    interval = BOX_INTERVALS.get(box, 1)
    return (date.today() + timedelta(days=interval)).isoformat()
