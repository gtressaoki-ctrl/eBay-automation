# eBay Automation — POD リサーチ〜出品〜収益ループ

在庫を持たずに、eBayでの商品リサーチ → デザイン生成 → 出品 → 受注 → 製造/発送手配
までを自動化し、得られた収益に応じて出品数を自動で増やしていく（=ループさせる）
パイプラインです。

## 仕組み

- **商材**: 11ozセラミックマグ（Printify Choice）。後述の需要計測で、同じ手間でも
  グラフィックTシャツの約12倍の「1出品あたり月間利益」が見込めたため選定しています。
- **需要リサーチ**: eBay Browse APIの `estimatedSoldQuantity`（出品ごとの推定販売数）
  と `itemCreationDate` から **「1出品が1ヶ月に何個売れているか」を実測**します。
  出品件数＝競合の数であって需要ではないため、件数ベースのスコアリングは使いません。
  販売価格も「実際に売れている出品の中央値」から決めます（原価×倍率ではない）。
  eBay公式の落札データは入手できません（Marketplace Insights APIは新規申請不可、
  Finding APIの `findCompletedItems` は2025年2月に廃止）。
- **利益フィルタ**: 市場価格 − eBay手数料(13.25%+$0.40) − 製造原価 − 送料 が
  `MIN_UNIT_PROFIT_CENTS` を下回るニッチは、どれだけ売れていても出品しません。
- **仕入れモデル**: Print-on-Demand（Printify）。買い手が注文するまで在庫を作らず、
  Printifyが製造パートナーとして買い手に直送します。eBayのドロップシッピング
  ポリシー上、**卸/製造パートナー経由は許可**されており、他マーケットプレイスから
  買って転送する「アービトラージ型」は一切行いません（詳細は `docs/SETUP.md` §0）。
- **出品**: eBay 公式 Sell API（Inventory API / Fulfillment API）を直接呼び出し。
  Printify純正のeBay連携（月額$99.99〜）は使わず、無料のPrintify APIを自前で
  組み合わせることで固定費ゼロで運用します。
- **承認フロー**: 出品直前（`publishOffer`）だけ人間の承認を挟みます
  （GitHub Issueに `/approve` / `/reject` とコメント）。安定運用後は
  `AUTO_PUBLISH=true` で完全自動化に切り替え可能です。
- **ループ**: このリポジトリの GitHub Actions が定期実行の起点です。
  リサーチ→出品→受注→発送→利益集計（`state/ledger.json`）→黒字なら翌日の
  出品数を自動で増やす、という循環になっています。

```
[毎日] research_and_list.yml
  → 需要実測(販売数/出品/月) → 利益フィルタ → デザイン生成
  → Printify商品作成 → eBay下書き出品 → 承認Issue作成（根拠の数字つき）

[Issueコメント] approve_listing.yml
  → /approve で実際にeBayへ公開 / /reject で破棄

[2時間毎] fulfill_orders.yml
  → 新規注文をPrintifyへ自動発注 → 追跡番号が付いたらeBayに発送済み反映
  → state/ledger.json に利益を記録 → 黒字なら翌日の出品数UP
```

## セットアップ

**先に `docs/SETUP.md` を読んでください。** eBay Developer登録・Printifyアカウント
作成・支払い方法登録など、本人確認や決済が絡む工程は自動化できないため手動で行う
必要があります。

## ローカル開発

```bash
pip install -r requirements.txt
cp .env.example .env  # 値を埋める
python -m pytest tests/
python -m ebay_automation.pipeline_research  # DRY_RUN=trueで下書きのみ確認可能
```

## ディレクトリ構成

- `src/ebay_automation/` — パイプライン本体（Pythonパッケージ）
  - `research.py` — 需要実測（販売数・売れている価格帯・利益フィルタ）
  - `themes.py` — 実際にプリントするデザイン内容（検索キーワードとは別物）
  - `design_gen.py` — プリント領域いっぱいに組版してPNG出力
- `.github/workflows/` — 定期実行・承認処理・受注同期のGitHub Actions
- `state/` — 実行状態（承認待ちリスト・注文台帳）。ワークフローが自動コミット
- `docs/SETUP.md` — 初期セットアップ手順（eBay/Printify/GitHub Secrets）
- `scripts/list_printify_catalog.py` — 出品するブランク商品のID調査用ツール

## ブランド化の方針

複数テーマを並行して探索する「探索フェーズ」と、1テーマに絞る「ブランド確立フェーズ」を
分けています。

- **探索フェーズ**（デフォルト）: `themes.py` の全テーマの需要を毎回測定し、利益フロアを
  超えたものから出品する。まだどれが本命か分からない段階。
- **ブランド確立フェーズ**: いずれかのテーマで **`BRAND_LOCK_MIN_PUBLISHED`件以上の公開済み
  出品が黒字**を記録すると、そのテーマ**だけ**に絞って以後のリサーチを続ける
  （`pipeline_research.select_active_themes`）。無関係なテーマを延々と並走させても、
  買い手に覚えてもらえる店にはならないため。

需要側（実売数・価格）は自動判定しますが、供給側（競合密度）は判定材料として承認Issueに
出すだけで、自動判定には使いません。件数だけで判断するのは初期バグの原因になったためです
（`research.py`のモジュールDocstring参照）。複数テーマが同時に黒字ラインを超えたときは、
競合出品数（Issueの表に記載）が少ない方を人が優先することを推奨します——同じ売上でも、
空いている市場の方が「そのジャンルの代表的な店」になりやすいためです。

**このパイプラインが自動化できない部分**（eBay Seller Hub上の手作業、または課金判断）:

- ショップ名・ロゴ・ストアバナーなどの見た目のブランディング（eBay Storeへの加入が必要、
  月額課金あり。デザインは Seller Hub の Web UI 操作のみで、公開APIがない）
- ショップ名を決めたら `BRAND_TAGLINE` に設定すると、以後の全リスティングの説明文と
  eBayの Brand item specific に自動で反映されます

## 既知の制約（v1）

- 1出品につきサイズ/カラーは1バリアントのみ（eBayのバリエーション出品は未対応）
- デザインはテンプレートベースのタイポグラフィのみ（画像生成モデルは未統合）。
  `themes.py` のデザインを使い切ると、その日は新規出品が止まります
- 需要計測は「現在出品中」の商品しか見られないため、売り切れた出品は
  サンプルから抜けます。出てくる数字は**常に実態より控えめ**の下限値です
- eBayカテゴリID・必須Item Specificsはデフォルト値のみで、カテゴリごとの詳細な
  必須項目チェックは未実装（実運用前にTaxonomy APIでの検証を推奨）
