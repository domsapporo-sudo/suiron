#!/usr/bin/env python3
"""
arXiv の週次投稿数を集計して data/arxiv_weekly.csv に1行追記する。

- 標準ライブラリのみで動く（pip install 不要）
- 同じ週の行が既にあれば何もしない（何度実行しても安全）
- arXiv API の作法に従い、リクエスト間に3秒あける

謝辞表記が必須:
  Thank you to arXiv for use of its open access interoperability.
"""

import csv
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

API = "http://export.arxiv.org/api/query"
NS = {"opensearch": "http://a9.com/-/spec/opensearch/1.1/"}

# 連絡先を入れておくのが API 利用の作法。自分のドメインに書き換えてください。
USER_AGENT = "suiron-indicator/0.1 (+https://example.jp; mailto:you@example.jp)"

CATEGORIES = ["cs.AI", "cs.CL", "cs.LG", "cs.CV", "cs.RO"]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "arxiv_weekly.csv")


def last_full_week(now=None):
    """直近の「終わった週」（月曜0時〜翌月曜0時）を UTC で返す。"""
    now = now or datetime.now(timezone.utc)
    this_monday = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start = this_monday - timedelta(days=7)
    return start, this_monday


def count(category, start, end):
    """指定カテゴリ・期間の投稿件数を返す。件数だけ欲しいので max_results=1。"""
    q = "cat:{} AND submittedDate:[{} TO {}]".format(
        category, start.strftime("%Y%m%d%H%M"), end.strftime("%Y%m%d%H%M")
    )
    url = "{}?{}".format(
        API, urllib.parse.urlencode({"search_query": q, "max_results": 1})
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as res:
        body = res.read()
    root = ET.fromstring(body)
    node = root.find("opensearch:totalResults", NS)
    if node is None or not (node.text or "").strip():
        raise RuntimeError("totalResults が取れませんでした: " + category)
    return int(node.text.strip())


def already_recorded(week_start):
    if not os.path.exists(OUT):
        return False
    with open(OUT, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("week_start") == week_start:
                return True
    return False


def main():
    start, end = last_full_week()
    week_start = start.strftime("%Y-%m-%d")

    if already_recorded(week_start):
        print("既に記録済みです: {}".format(week_start))
        return 0

    counts = {}
    for i, cat in enumerate(CATEGORIES):
        if i:
            time.sleep(3)  # arXiv のレート制限を守る
        counts[cat] = count(cat, start, end)
        print("{}: {}".format(cat, counts[cat]))

    header = ["week_start", "week_end"] + CATEGORIES + ["total", "collected_at"]
    row = {
        "week_start": week_start,
        "week_end": end.strftime("%Y-%m-%d"),
        "total": sum(counts.values()),
        "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    row.update(counts)

    is_new = not os.path.exists(OUT) or os.path.getsize(OUT) == 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if is_new:
            w.writeheader()
        w.writerow(row)

    print("追記しました: {} (合計 {})".format(week_start, row["total"]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 収集の失敗でワークフロー全体を止めない
        print("収集に失敗しました: {}".format(e), file=sys.stderr)
        sys.exit(0)
