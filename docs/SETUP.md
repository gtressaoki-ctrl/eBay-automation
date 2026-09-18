# セットアップ手順

このパイプラインを動かすには、本人確認・決済が絡む工程がいくつかあり、それらは
Claude Code では代行できません。以下を一度だけ手動で行ってください。

## 0. コンプライアンス方針（必ず理解してから進めてください）

- 採用するのは **Print-on-Demand (POD)**。Printify が「卸/製造パートナーとして
  買い手に直送する」役割を担うため、eBayのドロップシッピングポリシー上
  **許可されている**形態です。
- **禁止**なのは、Amazon/AliExpressなど「小売店・他マーケットプレイス」から
  購入して買い手に直送させる方式（アービトラージ型ドロップシッピング）。
  このリポジトリのコードは一切この方式を行いません。
- Printify 純正の eBay 連携機能は Empire プラン（$99.99/月）が必要なため、
  月額費用を避けるためにこのプロジェクトは **Printify の汎用APIを直接叩いて
  自前で eBay と連携**します。Printifyへの支払いは注文ごとの製造・送料の実費のみです。
- 注文が入るたびに Printify 側で実費が即時にカード請求されます（eBayからの入金より
  先に発生し得ます）。これは自動化できない「実ビジネスの資金」の話として認識してください。

## 1. eBay Developer Program 登録 & APIキー取得

1. https://developer.ebay.com でアカウント作成し、Developer Program に登録。
2. "Application Keys" で **Production** の Keyset を作成 → `App ID (Client ID)` /
   `Cert ID (Client Secret)` / `Dev ID` を控える。
3. Keyset の設定画面で **RuName**（redirect URL name）を作成する。
4. ユーザートークン（refresh token）を取得する。開発者ダッシュボードの
   "User Tokens" ツール（"Get A Token From eBay via Your Application"）を使うと
   ブラウザ操作だけで取得できます。同意画面で自分のeBay出品者アカウントでログインし、
   以下のスコープを許可してください:
   - `https://api.ebay.com/oauth/api_scope/sell.inventory`
   - `https://api.ebay.com/oauth/api_scope/sell.fulfillment`
   - `https://api.ebay.com/oauth/api_scope/sell.account`
   発行される **refresh token**（有効期限約18ヶ月）を控える。期限が切れたら
   同じ手順で再取得してください。
5. eBay Seller Hub で **Business Policies** を有効化（Account settings >
   Business policies）。送料・支払い・返品ポリシーを1つずつ作成。
6. 各ポリシーの ID を取得（Seller Hub の画面には出ないため、一度だけ Account API を叩く）:
   ```bash
   TOKEN=... # 上で取得したuser access token
   curl -H "Authorization: Bearer $TOKEN" \
     "https://api.ebay.com/sell/account/v1/fulfillment_policy?marketplace_id=EBAY_US"
   curl -H "Authorization: Bearer $TOKEN" \
     "https://api.ebay.com/sell/account/v1/payment_policy?marketplace_id=EBAY_US"
   curl -H "Authorization: Bearer $TOKEN" \
     "https://api.ebay.com/sell/account/v1/return_policy?marketplace_id=EBAY_US"
   ```
7. 発送元ロケーション（merchant location key）を作成:
   ```bash
   curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     "https://api.ebay.com/sell/inventory/v1/inventory_location/main-location" \
     -d '{"location": {"address": {"country": "US"}}, "locationTypes": ["WAREHOUSE"]}'
   ```
   ここで使った `main-location` が `EBAY_MERCHANT_LOCATION_KEY` になります。

## 2. Printify 設定

1. https://printify.com でアカウント作成（無料プランでOK）。支払い方法を登録
   （注文ごとの製造・送料が請求されます）。
2. ダッシュボードで新しいストアを追加する際、"Manual order platform" /
   "API" タイプのストアを選択（純正eBay連携=有料プランのものは選ばない）。
   作成後、そのストアの Shop ID を確認: `GET https://api.printify.com/v1/shops.json`
   （下の API トークンをBearerで付与）で一覧取得できます。
3. My Profile > Connections で **API トークン**を発行 → `PRINTIFY_API_KEY`。
4. 売りたいブランク商品（例: Tシャツ）を決める:
   ```bash
   PRINTIFY_API_KEY=xxx python scripts/list_printify_catalog.py
   PRINTIFY_API_KEY=xxx python scripts/list_printify_catalog.py --blueprint <id>
   ```
   出力された `blueprint_id` / `print_provider_id` / `variant_id` (複数可)を控える。

## 3. GitHub リポジトリの Secrets / Variables を設定

Settings > Secrets and variables > Actions で設定（`GITHUB_TOKEN` は自動付与のため不要）。

**Secrets**（暗号化・非公開）:
- `EBAY_APP_ID`, `EBAY_CERT_ID`, `EBAY_DEV_ID`, `EBAY_REFRESH_TOKEN`
- `PRINTIFY_API_KEY`

**Variables**（平文でOK）:
- `EBAY_MARKETPLACE_ID`（例: `EBAY_US`）, `EBAY_ENV`（`PRODUCTION`）, `EBAY_CATEGORY_ID`
- `EBAY_MERCHANT_LOCATION_KEY`, `EBAY_FULFILLMENT_POLICY_ID`, `EBAY_PAYMENT_POLICY_ID`, `EBAY_RETURN_POLICY_ID`
- `PRINTIFY_SHOP_ID`, `PRINTIFY_BLUEPRINT_ID`, `PRINTIFY_PRINT_PROVIDER_ID`, `PRINTIFY_VARIANT_IDS`（カンマ区切り）
- `DAILY_LISTING_QUOTA`（初期値 `3` 推奨）, `DEFAULT_MARKUP_MULTIPLIER`（初期値 `2.2`）, `DRY_RUN`（`false`）

## 4. 動作確認

1. GitHub Actions タブ → "eBay POD Research & Draft Listing" を手動実行
   (`workflow_dispatch`)。成功すると `pending-approval` ラベル付きの Issue が
   1〜数件作成されます（実際にはeBayへ**公開されません**、下書きのみ）。
2. Issue の内容（デザイン画像・価格・想定利益）を確認し、問題なければ
   Issue に `/approve` とコメント。数十秒後、自動でeBayに公開され、
   公開URLがコメントされます。問題があれば `/reject` で破棄。
3. 買い手が実際に購入すると、"eBay POD Order Fulfillment Sync" が
   2時間毎に注文を検知し、Printifyへ自動発注→追跡番号が付き次第eBayに
   発送済みとして反映します。
4. `state/ledger.json` に売上・原価・利益が蓄積され、黒字が続くと
   `daily_listing_quota` が自動で増えます（=収益ループの再投資部分）。

## 5. 完全自動化への移行

最初は Issue 承認を挟む設計です。安定して運用できたら、GitHub Variables で
`AUTO_PUBLISH=true` に切り替えるだけで、承認ステップを飛ばして即座にeBayへ
公開するモードになります（コード変更不要）。
