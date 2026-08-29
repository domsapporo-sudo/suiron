# 推論 / SUIRON — Phase 0

AI専門メディアの最小構成。**現金支出はドメイン代（年3,000〜4,000円）だけ**で動きます。

- 指標の収集 → GitHub Actions（無料）
- 生データの保存 → このリポジトリに CSV をコミット（履歴がそのまま改ざん防止の証拠になる）
- サイトのビルドと配信 → Cloudflare Pages（無料）

**あなたのPCには何もインストールしなくて構いません。**Python も Node.js も、
GitHub と Cloudflare のサーバー側で動きます。

---

## 中身

```
scripts/          収集スクリプト（Python標準ライブラリのみ / pip install 不要）
  collect_pricing.py   推論コスト（OpenRouter・毎日）
  collect_arxiv.py     論文投稿数（arXiv・週次）
  collect_rss.py       編集部ネタ帳（RSS巡回・毎日）
sources/feeds.txt  巡回するRSSの一覧。ここを育てていく
data/             収集した生データ。公開する
  digest/         ネタ帳。記事の候補（公開しない前提だが、リポジトリが公開なら見えるので注意）
src/              サイト本体（Astro）
  pages/posts/    記事の Markdown を置く場所
  pages/method.astro  算出方法・編集方針（★ここを最初に埋める）
.github/workflows/collect.yml  毎朝6時(JST)に収集してコミットする
```

---

## 立ち上げ手順

### 1. GitHub にリポジトリを作って push する

**パブリックリポジトリを推奨します。**理由は2つ。

- GitHub Actions の実行時間がパブリックなら実質無制限（プライベートは月2,000分）
- 生データが公開されること自体が、指標の信頼性の裏付けになる

ただし `data/digest/` のネタ帳も見えるので、隠したいならその行を `.gitignore` に足してください。

### 2. Actions を1回手動で走らせる

リポジトリの **Actions タブ → collect → Run workflow**。

- `inference_cost.csv` に1行入ります（当日分）
- `arxiv_weekly.csv` は「終わった週」がないと入りません。初回は空のままでも正常です
- `data/digest/YYYY-MM-DD.json` にネタ帳ができます

ログに `SKIP` が出るフィードは、URLが変わったか落ちています。放置して構いません。
`sources/feeds.txt` から消すか差し替えてください。

### 3. Cloudflare Pages につなぐ

Cloudflare ダッシュボード → Workers & Pages → Pages → Git を接続。

| 設定 | 値 |
|---|---|
| フレームワーク | Astro |
| ビルドコマンド | `npm run build` |
| 出力ディレクトリ | `dist` |

これで push のたびに自動でビルドされます。Actions が毎朝データをコミットするので、
**指標も自動で最新になります。**

### 4. 埋める場所（3か所）

| ファイル | 直すところ |
|---|---|
| `src/pages/method.astro` | 【あなたの名前】、経歴、メールアドレス |
| `astro.config.mjs` | `site` を実際のドメインに |
| `scripts/*.py` の `USER_AGENT` | 連絡先。APIを叩くときの作法です |

---

## 記事の書き方

`src/pages/posts/` に Markdown を追加すると、トップに自動で並びます。
`example.md` をコピーして使ってください。フロントマターに必ず入れるもの：

```yaml
sources:              # 一次情報。ここが空の記事は出さない
  - label: 会見資料（PDF）
    url: https://...
author: あなたの名前   # 実在する人だけ
published: 2026-08-29
updated: 2026-08-29
review: 2026-09-30    # 次回見直し予定
```

この3つはコストゼロで、他のAI系メディアの多くがやっていません。初日から差がつきます。

---

## 日々の運用（週15〜20時間）

| | やること | 時間 |
|---|---|---|
| 毎朝 | `data/digest/` の最新JSONを見る。`cross_source_terms`（複数媒体が触れている語）が取材の合図 | 10分 |
| 火・水・木 | 記事を1本ずつ | 各3〜4時間 |
| 金 | 週次まとめと仕込み | 1時間 |

---

## ローカルで動かしたい場合（任意）

Node.js 18以上を入れてから：

```bash
npm install
npm run dev
```

収集スクリプトを手元で試すなら Python 3.10以上を入れて：

```bash
python scripts/collect_pricing.py
python scripts/collect_rss.py
```

どちらも不要です。GitHub と Cloudflare だけで完結します。

---

## 守ること

- **架空の編集部を作らない。**一人なら一人と書く。監修者がいないなら「監修なし」でいい。
  嘘の体制は、Googleにも読者にもいずれ露見して媒体が終わります
- **指標の定義を後から変えない。**変えるならこのページに変更日と内容を追記し、過去の値は遡らない
- **他媒体の見出しや本文を転載しない。**見出しにも著作権が認められた判例があります
- **集計をLLMにさせない。**抽出まではAI、数えるのはコード

---

## 出所と謝辞

- 論文数：arXiv 公開API。`Thank you to arXiv for use of its open access interoperability.`
  商用利用の条件は arXiv のドキュメントを必ず自分で確認してください
- 推論コスト：OpenRouter の公開モデル一覧（認証不要）
- 各APIの利用条件は変わります。公開前にもう一度確認を
