#!/usr/bin/env python3
"""
RSS/Atom を巡回して「編集部ネタ帳」を data/digest/YYYY-MM-DD.json に書く。

これは公開しない。記事を書くための候補リスト。
複数の情報源が同じ語を扱っていたら、それが取材に動く合図。

- 標準ライブラリのみ（pip install 不要）
- 落ちているフィードはスキップして続行する
- 見出しは記事にそのまま使わないこと（自分の言葉で書き直す）
"""

import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone

USER_AGENT = "suiron-reader/0.1 (+https://example.jp)"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEEDS = os.path.join(ROOT, "sources", "feeds.txt")
OUTDIR = os.path.join(ROOT, "data", "digest")

# 頻度を数えても意味のない語
STOP = set(
    """
the a an of for and or to in on at with from by is are be as it its this that
新しい こと もの ため それ これ など および また さらに という 発表 提供 開始 実現 対応 可能
""".split()
)

TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9\-\.\+]{2,}|[ぁ-んァ-ヴー一-龠]{2,}")


def load_feeds():
    if not os.path.exists(FEEDS):
        return []
    urls = []
    with open(FEEDS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls


def strip_ns(tag):
    return tag.split("}", 1)[-1] if "}" in tag else tag


def parse(xml_bytes):
    """RSS 2.0 と Atom の両方から (title, link) を拾う。"""
    items = []
    root = ET.fromstring(xml_bytes)
    for el in root.iter():
        if strip_ns(el.tag) not in ("item", "entry"):
            continue
        title, link = None, None
        for child in el:
            name = strip_ns(child.tag)
            if name == "title" and child.text:
                title = " ".join(child.text.split())
            elif name == "link":
                # Atom は href 属性、RSS はテキスト
                link = child.get("href") or (child.text or "").strip() or link
        if title:
            items.append({"title": title, "link": link or ""})
    return items


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read()


def main():
    urls = load_feeds()
    if not urls:
        print("sources/feeds.txt が空です")
        return 0

    entries = []
    seen_links = set()
    ok, ng = 0, 0

    for url in urls:
        try:
            items = parse(fetch(url))
            source = re.sub(r"^www\.", "", (url.split("/")[2] if "//" in url else url))
            for it in items[:30]:
                key = it["link"] or it["title"]
                if key in seen_links:
                    continue
                seen_links.add(key)
                it["source"] = source
                entries.append(it)
            ok += 1
            print("OK   {} ({}件)".format(url, len(items)))
        except Exception as e:
            ng += 1
            print("SKIP {} -> {}".format(url, e), file=sys.stderr)

    # 語ごとに「いくつの情報源が触れているか」を数える。
    # 同じ語を1つの媒体が連呼しても1と数えるのが肝。
    sources_by_term = defaultdict(set)
    for e in entries:
        for t in set(TOKEN.findall(e["title"])):
            t_norm = t.lower()
            if t_norm in STOP or len(t_norm) < 2:
                continue
            sources_by_term[t_norm].add(e["source"])

    cross = Counter({t: len(s) for t, s in sources_by_term.items() if len(s) >= 2})

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, "{}.json".format(today))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(
            {
                "date": today,
                "feeds_ok": ok,
                "feeds_failed": ng,
                "entries": entries,
                "cross_source_terms": cross.most_common(40),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("\n--- 複数の情報源が触れている語 ---")
    for term, n in cross.most_common(15):
        print("  {:>2} 媒体  {}".format(n, term))
    print("\n{} 件を {} に書きました".format(len(entries), out))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("収集に失敗しました: {}".format(e), file=sys.stderr)
        sys.exit(0)
