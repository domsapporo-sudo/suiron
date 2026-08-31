#!/usr/bin/env python3
"""
RSS/Atom を巡回して「編集部ネタ帳」を作る。

■ 何を見つけるか
  1. 同じ記事URLを、複数の情報源が取り上げているか  ← 最重要シグナル
  2. 同じ語を、複数の情報源が使っているか            ← 補助

  1が効くのは、はてなブックマークやHacker Newsが「元記事のURL」を
  そのまま指すためです。メディアが出した記事がはてブでも伸びていれば、
  2つの情報源が同じURLを指すので自動で検出できます。
  Xを見に行かなくても「いま話題のもの」が分かる、という設計です。

■ 出力
  data/digest/YYYY-MM-DD.json  … 機械用（下書き生成が読む）
  data/digest/latest.md        … 人が毎朝読む用

■ 決まりごと
  これは「気づくため」の道具です。ここから引用せず、
  必ずリンク先の一次情報にあたって、自分の言葉で書くこと。
"""

import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone

USER_AGENT = "suiron-reader/0.2 (+https://suiron-1rk.pages.dev)"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEEDS = os.path.join(ROOT, "sources", "feeds.txt")
OUTDIR = os.path.join(ROOT, "data", "digest")

# 数えても意味のない語。英語の機能語をしっかり落とすのが肝。
STOP = set("""
a an the this that these those it its it's is are was were be been being am
of for and or but nor so yet to in on at by with from into over under about
as if then than when while where how what which who whom whose why
i you he she we they me him her us them my your his our their
not no yes can could will would shall should may might must do does did done
have has had get gets got make makes made use uses used using new now here
more most less least very just also only even still back out up down off
all any some each every both few many much other another same such own
one two three first last next best top great good big small
new news blog post posts article articles update updates via read
show ask tell say says said see look via free open source code app apps
ai llm llms model models data tech
こと もの ため それ これ その この あの どの など および また さらに という
発表 提供 開始 実現 対応 可能 詳細 こちら 記事 続き 公開 導入 活用 利用
方法 場合 必要 実施 予定 検討 今回 今週 本日 最新 注目 話題 まとめ
""".split())

TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9\-\.\+]{2,}|[ぁ-んァ-ヴー一-龠]{2,}")
TRACK = re.compile(r"[?&](utm_[^=&]*|fbclid|gclid|srsltid|ref|source|spm)=[^&]*", re.I)


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


def host_of(url):
    m = re.match(r"https?://([^/]+)", url or "")
    return re.sub(r"^www\.", "", m.group(1)).lower() if m else (url or "")


def norm_link(url):
    """比較用にURLを正規化する。表示には元のURLを使う。"""
    if not url:
        return ""
    u = url.split("#")[0]
    u = TRACK.sub("", u)
    u = re.sub(r"[?&]+$", "", u)
    u = re.sub(r"/+$", "", u)
    return u.lower()


def parse(xml_bytes):
    """RSS 2.0 / RSS 1.0(RDF) / Atom から (title, link) を拾う。"""
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
    seen = set()
    ok, ng = 0, 0
    per_source = defaultdict(list)

    for url in urls:
        source = host_of(url)
        try:
            items = parse(fetch(url))
        except Exception as e:
            ng += 1
            print("SKIP {} -> {}".format(url, e), file=sys.stderr)
            continue
        ok += 1
        print("OK   {} ({}件)".format(url, len(items)))
        for it in items[:40]:
            key = (source, it["link"] or it["title"])
            if key in seen:
                continue
            seen.add(key)
            it["source"] = source
            it["norm"] = norm_link(it["link"])
            entries.append(it)
            per_source[source].append(it)

    # --- ① 同じ記事URLを、いくつの情報源が指しているか ---
    by_link = defaultdict(lambda: {"sources": set(), "title": "", "url": ""})
    for e in entries:
        n = e["norm"]
        if not n or "news.google.com" in n:   # Googleニュースは中継URLなので照合できない
            continue
        rec = by_link[n]
        rec["sources"].add(e["source"])
        if not rec["title"]:
            rec["title"] = e["title"]
            rec["url"] = e["link"]

    cross_links = sorted(
        [
            {"url": r["url"], "title": r["title"],
             "sources": sorted(r["sources"]), "count": len(r["sources"])}
            for r in by_link.values() if len(r["sources"]) >= 2
        ],
        key=lambda r: -r["count"],
    )[:30]

    # --- ② 同じ語を、いくつの情報源が使っているか ---
    src_by_term = defaultdict(set)
    for e in entries:
        for t in set(TOKEN.findall(e["title"])):
            k = t.lower()
            if k in STOP or len(k) < 2:
                continue
            src_by_term[k].add(e["source"])
    cross_terms = sorted(
        [(t, len(s)) for t, s in src_by_term.items() if len(s) >= 3],
        key=lambda x: -x[1],
    )[:40]

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    os.makedirs(OUTDIR, exist_ok=True)

    with open(os.path.join(OUTDIR, "{}.json".format(today)), "w", encoding="utf-8") as f:
        json.dump({
            "date": today, "feeds_ok": ok, "feeds_failed": ng,
            "entries": entries,
            "cross_source_links": cross_links,
            "cross_source_terms": cross_terms,
        }, f, ensure_ascii=False, indent=2)

    # --- 人が毎朝読む用 ---
    md = []
    md.append("# ネタ帳 {}".format(today))
    md.append("")
    md.append("フィード {}本成功 / {}本失敗　記事 {}件".format(ok, ng, len(entries)))
    md.append("")
    md.append("> ここから引用しないこと。リンク先の一次情報にあたって、自分の言葉で書く。")
    md.append("")

    md.append("## 複数の情報源が扱っている記事（取材候補）")
    md.append("")
    if cross_links:
        for r in cross_links:
            md.append("- **{}媒体** [{}]({})".format(r["count"], r["title"], r["url"]))
            md.append("  　`{}`".format(" / ".join(r["sources"])))
    else:
        md.append("今日は重なりがありませんでした。")
    md.append("")

    md.append("## 複数の情報源が使っている語")
    md.append("")
    if cross_terms:
        md.append("| 語 | 情報源の数 |")
        md.append("|---|---|")
        for t, n in cross_terms[:25]:
            md.append("| {} | {} |".format(t, n))
    else:
        md.append("該当なし。")
    md.append("")

    md.append("## 新着（情報源ごとに5件まで）")
    md.append("")
    for source in sorted(per_source):
        md.append("### {}".format(source))
        for it in per_source[source][:5]:
            if it["link"]:
                md.append("- [{}]({})".format(it["title"], it["link"]))
            else:
                md.append("- {}".format(it["title"]))
        md.append("")

    with open(os.path.join(OUTDIR, "latest.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md))

    print("\n--- 複数の情報源が扱っている記事 ---")
    for r in cross_links[:10]:
        print("  {}媒体  {}".format(r["count"], r["title"][:60]))
    print("\n{}件を書き出しました（フィード {}成功 / {}失敗）".format(len(entries), ok, ng))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("収集に失敗しました: {}".format(e), file=sys.stderr)
        sys.exit(0)
