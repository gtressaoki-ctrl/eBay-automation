# eBay Automation — POD リサーチ〜出品〜収益ループ

在庫を持たずに、eBayでの商品リサーチ → デザイン生成 → 出品 → 受注 → 製造/発送手配
までを自動化し、得られた収益に応じて出品数を自動で増やしていく（=ループさせる）
パイプラインです。

## 仕組み

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
  → ニッチ調査 → デザイン生成 → Printify商品作成 → eBay下書き出品 → 承認Issue作成

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
- `.github/workflows/` — 定期実行・承認処理・受注同期のGitHub Actions
- `state/` — 実行状態（承認待ちリスト・注文台帳）。ワークフローが自動コミット
- `docs/SETUP.md` — 初期セットアップ手順（eBay/Printify/GitHub Secrets）
- `scripts/list_printify_catalog.py` — 出品するブランク商品のID調査用ツール

## 既知の制約（v1）

- 1出品につきサイズ/カラーは1バリアントのみ（eBayのバリエーション出品は未対応）
- デザインはテンプレートベースのタイポグラフィのみ（画像生成モデルは未統合）
- eBayカテゴリID・必須Item Specificsはデフォルト値のみで、カテゴリごとの詳細な
  必須項目チェックは未実装（実運用前にTaxonomy APIでの検証を推奨）
