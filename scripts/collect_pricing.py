#!/usr/bin/env python3
"""
推論コスト指数を1日1行、data/inference_cost.csv に追記する。

出所: OpenRouter の公開モデル一覧 https://openrouter.ai/api/v1/models
      （認証不要。pricing.prompt / pricing.completion は USD/トークン）

■ 算出方法（これをそのまま /method ページに載せること）
  1. pricing.prompt > 0 のモデルだけを対象にする（無料モデルは除外）
  2. 各モデルの入力単価を USD / 100万トークン に換算する
  3. 対象全モデルの中央値・第1四分位・第3四分位を出す
  4. 中央値を指数の本体とし、対象モデル数も併せて記録する

  中央値を使うのは、極端に高い/安いモデルに引きずられないため。
  平均に変えると数字が動くので、定義を変えるときは必ず注記すること。
"""

import csv
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

API = "https://openrouter.ai/api/v1/models"
USER_AGENT = "suiron-indicator/0.1 (+https://example.jp)"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "inference_cost.csv")


def quantile(values, q):
    """線形補間つきの分位点。numpy を使わずに済ませる。"""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * q
    low = int(pos)
    high = min(low + 1, len(s) - 1)
    frac = pos - low
    return s[low] + (s[high] - s[low]) * frac


def fetch():
    req = urllib.request.Request(API, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read().decode("utf-8"))


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def already_recorded(day):
    if not os.path.exists(OUT):
        return False
    with open(OUT, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("date") == day:
                return True
    return False


def main():
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if already_recorded(day):
        print("既に記録済みです: {}".format(day))
        return 0

    payload = fetch()
    models = payload.get("data", payload if isinstance(payload, list) else [])

    prompt_prices = []
    completion_prices = []
    for m in models:
        pricing = m.get("pricing") or {}
        p = to_float(pricing.get("prompt"))
        c = to_float(pricing.get("completion"))
        if p > 0:
            prompt_prices.append(p * 1_000_000)  # USD / 1M tokens
        if c > 0:
            completion_prices.append(c * 1_000_000)

    if not prompt_prices:
        raise RuntimeError("価格の取れたモデルが0件でした")

    row = {
        "date": day,
        "input_median": round(quantile(prompt_prices, 0.5), 4),
        "input_q1": round(quantile(prompt_prices, 0.25), 4),
        "input_q3": round(quantile(prompt_prices, 0.75), 4),
        "output_median": round(quantile(completion_prices, 0.5), 4),
        "models": len(prompt_prices),
        "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    header = list(row.keys())
    is_new = not os.path.exists(OUT) or os.path.getsize(OUT) == 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if is_new:
            w.writeheader()
        w.writerow(row)

    print(
        "追記しました: {} 入力中央値 ${}/1M ({}モデル)".format(
            day, row["input_median"], row["models"]
        )
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("収集に失敗しました: {}".format(e), file=sys.stderr)
        sys.exit(0)
