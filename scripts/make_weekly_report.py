#!/usr/bin/env python3
"""
週次の指標レポート記事を自動生成する。

自社で測ったデータを文章にするだけなので、機械が書いて問題ありません。
ただし「この数字をどう読むか」は空欄にしてあります。そこは人が書いてください。

- 標準ライブラリのみ（pip install 不要）
- 同じ週のファイルが既にあれば何もしない
- 既定では下書き（draft: true）として作る。中身を確認して公開する運用。
"""

import csv
import os
import sys
from datetime import datetime, timedelta, timezone

# True にすると、確認なしでいきなり公開されます。
# しばらく中身を見て、問題ないと思えたら True に変えてください。
PUBLISH_DIRECTLY = False

AUTHOR = "K"
AUTHOR_ROLE = "編集・執筆"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
POSTS = os.path.join(ROOT, "src", "pages", "posts")


def read_csv(name):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(row, key):
    try:
        return float(row[key])
    except (TypeError, ValueError, KeyError):
        return None


def pct(now, before):
    if now is None or before is None or before == 0:
        return None
    return (now - before) / before * 100


def arrow(p):
    if p is None:
        return "—"
    if p > 0:
        return "＋{:.1f}%".format(p)
    return "{:.1f}%".format(p)


def describe(p, up_word, down_word, flat_word="ほぼ横ばいだった"):
    """変化率を日本語にする。0.5%未満は横ばい扱い。"""
    if p is None:
        return "前週のデータがないため比較できない"
    if abs(p) < 0.5:
        return flat_word
    return "{}（{}）".format(up_word if p > 0 else down_word, arrow(p))


def main():
    cost = read_csv("inference_cost.csv")
    arxiv = read_csv("arxiv_weekly.csv")

    if not cost:
        print("推論コストのデータがまだありません。生成をスキップします。")
        return 0

    now = datetime.now(timezone.utc)
    iso_year, iso_week, _ = now.isocalendar()
    slug = "weekly-{}-w{:02d}".format(iso_year, iso_week)
    prefix = "" if PUBLISH_DIRECTLY else "_"
    path = os.path.join(POSTS, "{}{}.md".format(prefix, slug))

    if os.path.exists(path) or os.path.exists(os.path.join(POSTS, slug + ".md")):
        print("今週分は既にあります: {}".format(slug))
        return 0

    # --- 推論コスト：最新と、7営業日ぶんさかのぼった行 ---
    latest = cost[-1]
    prev = cost[-8] if len(cost) >= 8 else (cost[0] if len(cost) >= 2 else None)

    c_now = num(latest, "input_median")
    c_before = num(prev, "input_median") if prev else None
    c_pct = pct(c_now, c_before)
    out_now = num(latest, "output_median")
    q1, q3 = num(latest, "input_q1"), num(latest, "input_q3")
    models = latest.get("models", "—")

    # --- 論文投稿数 ---
    a_latest = arxiv[-1] if arxiv else None
    a_prev = arxiv[-2] if len(arxiv) >= 2 else None
    a_now = num(a_latest, "total") if a_latest else None
    a_before = num(a_prev, "total") if a_prev else None
    a_pct = pct(a_now, a_before)

    today = now.strftime("%Y-%m-%d")
    review = (now + timedelta(days=90)).strftime("%Y-%m-%d")
    title = "週次AI指標　{}年 第{}週".format(iso_year, iso_week)

    lines = []
    lines.append("---")
    lines.append("layout: ../../layouts/Post.astro")
    lines.append('title: "{}"'.format(title))
    lines.append(
        'description: "推論コストの入力中央値は${:.2f}／100万トークン。'
        '編集部が毎日測っている指標の週次まとめです。"'.format(c_now or 0)
    )
    lines.append("category: インデックス")
    lines.append("author: {}".format(AUTHOR))
    lines.append("authorRole: {}".format(AUTHOR_ROLE))
    lines.append('published: "{}"'.format(today))
    lines.append('updated: "{}"'.format(today))
    lines.append('review: "{}"'.format(review))
    if not PUBLISH_DIRECTLY:
        lines.append("draft: true")
    lines.append("sources:")
    lines.append("  - label: 指標の生データ（CSV）")
    lines.append(
        "    url: https://github.com/domsapporo-sudo/suiron/blob/main/data/inference_cost.csv"
    )
    lines.append("  - label: 算出方法")
    lines.append("    url: /method/")
    lines.append("---")
    lines.append("")

    lines.append(
        "編集部が毎日測っている指標の、今週分のまとめです。"
        "数値の算出方法と生データは[算出方法のページ](/method/)で公開しています。"
    )
    lines.append("")

    lines.append("## 推論コスト")
    lines.append("")
    lines.append("| 項目 | 値 |")
    lines.append("|---|---|")
    lines.append("| 入力 中央値 | ${:.2f} / 100万トークン |".format(c_now or 0))
    lines.append("| 出力 中央値 | ${:.2f} / 100万トークン |".format(out_now or 0))
    lines.append("| 第1四分位 〜 第3四分位 | ${:.2f} 〜 ${:.2f} |".format(q1 or 0, q3 or 0))
    lines.append("| 対象モデル数 | {} |".format(models))
    lines.append("| 前週比 | {} |".format(arrow(c_pct)))
    lines.append("")
    lines.append(
        "{}時点で、有料モデル{}件の入力単価の中央値は100万トークンあたり${:.2f}。"
        "前週から{}。".format(
            latest.get("date", today), models, c_now or 0,
            describe(c_pct, "上昇した", "下落した"),
        )
    )
    lines.append("")
    if q1 and q3 and q1 > 0:
        lines.append(
            "上位と下位の開きは{:.1f}倍（第1四分位${:.2f}、第3四分位${:.2f}）。"
            "同じ「AIの料金」といっても、選ぶモデルで一桁変わる状態が続いている。".format(
                q3 / q1, q1, q3
            )
        )
        lines.append("")

    lines.append("## 論文投稿数（週次）")
    lines.append("")
    if a_latest:
        lines.append("| 分野 | 本数 |")
        lines.append("|---|---|")
        for cat in ["cs.AI", "cs.CL", "cs.LG", "cs.CV", "cs.RO"]:
            lines.append("| {} | {} |".format(cat, a_latest.get(cat, "—")))
        lines.append("| **合計（延べ）** | **{}** |".format(a_latest.get("total", "—")))
        lines.append("")
        lines.append(
            "{}の週にarXivへ投稿された主要5分野の本数は、延べ{}本。前週から{}。".format(
                a_latest.get("week_start", "—"),
                a_latest.get("total", "—"),
                describe(a_pct, "増えた", "減った"),
            )
        )
    else:
        lines.append("今週はまだ確定した週次データがありません。次回の集計で掲載します。")
    lines.append("")

    lines.append("## この数字の読み方")
    lines.append("")
    lines.append("<!-- ここは人が書く。書かないまま公開しないこと。 -->")
    lines.append("（今週の数字で気づいたことを3〜4行。")
    lines.append("　なぜその動きが起きたのか、誰にとって効くのかを書く）")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**訂正・更新履歴**")
    lines.append("なし")
    lines.append("")

    os.makedirs(POSTS, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))

    print("作成しました: {}".format(os.path.relpath(path, ROOT)))
    if not PUBLISH_DIRECTLY:
        print("下書きです。ファイル名の先頭の _ を外し、draft: true の行を消すと公開されます。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("生成に失敗しました: {}".format(e), file=sys.stderr)
        sys.exit(0)
