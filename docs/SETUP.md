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

- **日本からの輸出（受注後仕入れ）** も扱います（`export_research.py`）。売れてから
  国内のショップで購入し、**必ず自分（または契約した発送代行）が受け取って検品・梱包し、
  自分で発送**します。国内ショップから海外の買い手へ直送させる形は、上記の禁止形態に
  当たるので行いません。中古品を仕入れて売る場合は**古物商許可**が必要です。

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
   - `https://api.ebay.com/oauth/api_scope/sell.marketing`（Promoted Listings用。
     `PROMOTED_LISTINGS_ENABLED`を使わないなら省略可だが、後から有効化する時に
     このトークンだと失敗するだけなので、取れるなら今のうちに含めておく）
   発行される **refresh token**（有効期限約18ヶ月）を控える。期限が切れたら、
   あるいは `invalid_grant`（"issued to another client" 等)エラーで全リクエストが
   失敗するようになったら、同じ手順で再取得してください。後者はキーセットの
   再生成やトークンの取り消しでも起こり得ます。
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
4. 売りたいブランク商品を決める。**初期設定は11ozセラミックマグ**
   (`blueprint_id=478` / `print_provider_id=99` / `variant_id=65216`)で、
   このままなら設定不要です。需要調査の結果、同じ価格帯でもマグの方が
   グラフィックTシャツより1出品あたりの月間利益が約12倍あったため
   デフォルト商材にしています。別の商材にする場合のみ:
   ```bash
   PRINTIFY_API_KEY=xxx python scripts/list_printify_catalog.py
   PRINTIFY_API_KEY=xxx python scripts/list_printify_catalog.py --blueprint <id>
   ```
   出力された `blueprint_id` / `print_provider_id` / `variant_id` (複数可)を控える。
   商材を変えたら `EBAY_CATEGORY_ID` と `SHIPPING_COST_CENTS` も合わせて変更する。

## 3. GitHub リポジトリの Secrets / Variables を設定

Settings > Secrets and variables > Actions で設定（`GITHUB_TOKEN` は自動付与のため不要）。

**Secrets**（暗号化・非公開）:
- `EBAY_APP_ID`, `EBAY_CERT_ID`, `EBAY_DEV_ID`, `EBAY_REFRESH_TOKEN`
- `PRINTIFY_API_KEY`

**Variables**（平文でOK）:
- `EBAY_MARKETPLACE_ID`（例: `EBAY_US`）, `EBAY_ENV`（`PRODUCTION`）,
  `EBAY_CATEGORY_ID`（マグは `20675`）
- `EBAY_MERCHANT_LOCATION_KEY`, `EBAY_FULFILLMENT_POLICY_ID`, `EBAY_PAYMENT_POLICY_ID`, `EBAY_RETURN_POLICY_ID`
- `PRINTIFY_SHOP_ID`, `PRINTIFY_BLUEPRINT_ID`（`478`）,
  `PRINTIFY_PRINT_PROVIDER_ID`（`99`）, `PRINTIFY_VARIANT_IDS`（`65216`、カンマ区切りで複数可）
- `DAILY_LISTING_QUOTA`（初期値 `3` 推奨）, `DRY_RUN`（`false`）
- `LISTING_QUANTITY`（初期値 `1`、登録不要）。新規セラーには「月◯個・$◯まで」の
  出品上限があり、**数量×価格**で消費される。受注生産なので在庫1で十分
  （売れたら受注同期が自動で1に戻す）。上限は Seller Hub の
  "Selling limits" から無料で引き上げ申請できる。
- `MIN_UNIT_PROFIT_CENTS`（初期値 `10`。新規セラーは実績づくり優先のため低め。
  黒字化したら引き上げる）, `SHIPPING_COST_CENTS`（送料を購入者負担にしている場合は `77`=送料にかかるeBay手数料分、送料無料なら `579`）
- `BRAND_LOCK_MIN_PUBLISHED`（初期値 `3`）, `BRAND_TAGLINE`（ショップ名を決めたら設定、未設定でOK）
- `PROMOTED_LISTINGS_ENABLED`（`true`で成約課金広告を有効化。README「新規セラーが
  誰の目にも留まらない問題」参照）, `PROMOTED_LISTINGS_BID_PERCENTAGE`（初期値 `10.0`）,
  `PROMOTED_LISTINGS_CAMPAIGN_NAME`（未設定でOK）

> 上表のうち `EBAY_*_POLICY_ID` / `EBAY_MERCHANT_LOCATION_KEY` / `PRINTIFY_SHOP_ID`
> は必須です。それ以外（商材・利益フロア等）は**登録しなければコード側の
> デフォルト（マグ）が使われる**ので、変更したいときだけ登録してください。
> 空文字で登録した場合もデフォルトにフォールバックします。
>
> **商材を変えたのに古い値が Variables に残っていると、そちらが優先されます。**
> 実行ログ冒頭の `Product: blueprint ... / eBay category ...` の行で、
> 実際に何を出品しようとしているか確認できます。

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

## 6. 日本からの輸出リサーチ（ジャンル候補の計測）

`Japan Export Research` ワークフロー（毎週月曜 06:00 JST、手動実行も可）が、ジャンルごとに
日本発送のeBay出品の売れ行きを実測し、`reports/export_research.md` に結果を書き出します。
出品も購入も一切しません。

1. https://e.developer.yahoo.co.jp/register でアプリケーションを登録し（Yahoo! JAPAN IDが必要、無料）、
   **Client ID** を控える。
2. GitHub の Secrets に `YAHOO_APP_ID` = Client ID を追加。
   未設定でも動きますが、その場合は需要だけでジャンルを並べ、仕入れ価格は照合しません。
3. 必要に応じて Variables を調整（未設定なら既定値）:
   - `EXPORT_SHIPPING_SMALL_JPY` / `_MEDIUM_JPY` / `_LARGE_JPY` — 国際送料（梱包込み）の概算。
     既定は 2200 / 3800 / 6500 円。契約した配送サービスの実料金に合わせてください。
   - `EXPORT_MIN_PROFIT_JPY` — 1個あたりの最低利益（既定 1500円）
   - `EXPORT_TAX_REFUND=true` — 課税事業者になり、輸出消費税の還付を受けられるようになったら
   - `EXPORT_FEE_RATE`（既定 0.1525 = 落札手数料13.6% + 海外手数料1.65%）、`EXPORT_FX_HAIRCUT`（既定 3%）
4. Actions → Japan Export Research → Run workflow。

## 7. 日本からの輸出出品（受注後仕入れ）

`export_listing.py` / `export_sync.py` / `export_commands.py` が、ベイブレードX（既定）を
「売れてから国内で買って、自分で発送する」形で出品します。

### 流れ
1. **毎朝 07:30 JST**（Japan Export Listing）: 日本発送で実際に売れている商品を探し、
   同じJANの日本発送最安値より少し下の価格で、Yahoo!ショッピングの最安在庫から
   `EXPORT_MIN_PROFIT_JPY` 以上の利益が出るものだけ下書きを作り、`[輸出・承認待ち]` Issueを開く。
   写真と商品情報は **eBayカタログの公式ストック写真** を使う（他の出品者の写真は使わない）。
2. Issueに `/approve` とコメントすると、仕入れ先の在庫を再確認してから公開。`/reject` で削除。
   - **eBayカタログに公式写真がない商品**は、代わりに `[輸出・写真待ち]` Issueになる（1日 `EXPORT_DAILY_PHOTO_REQUESTS` 件まで、既定2）。
     その商品を **1個だけ買い**、届いたら3〜8枚撮って、Issueに写真をドラッグ＆ドロップし、同じコメントに `/photos` と書いて送る。
     写真はeBayの画像サーバー（EPS）にアップロードされ、そのまま出品・公開される。手元の1個がまず売れ、
     その後は同じ写真で受注後仕入れを続ける。タイトルを変えたいときは `/photos` の次の行に `title: 新しいタイトル`。
     見送るなら `/reject`（その商品は今後も候補に出ない）。
   - 他の出品者・メーカーの写真は使わない（eBayの画像ポリシーと著作権のため）。AIで手を加えるのは、自分で撮った写真の
     背景や明るさの調整まで。
3. **2時間ごと**（Japan Export Sync）:
   - 仕入れ先が在庫切れ、または値上がりで利益が下限を割ったら、出品を **在庫0（購入不可）** にする。戻ったら1に戻す。
   - 新しい注文が入ったら `[仕入れ]` Issueを開く（買う場所・想定利益つき）。
     **購入者の氏名・住所はIssueに書かない**（このリポジトリは公開のため）。Seller Hubで確認する。
4. 仕入れて、**自分の住所で受け取り**、検品・梱包して発送したら、Issueに
   `/shipped japanpost EJ123456789JP 2480`（運送会社・追跡番号・実際の仕入れ値（円、省略可））とコメントする。
   eBayに発送済みとして登録され、利益が記録される。

### 一度だけ必要な設定
1. **Seller Hubで日本発送用の配送ポリシー**を作る（Account → Business policies → Shipping）
   - 名前: 例 `Japan export`
   - ハンドリングタイム: **5営業日**（仕入れ〜受け取り〜梱包の時間。変えたら `EXPORT_HANDLING_DAYS` も合わせる）
   - 国際配送: 送料は **無料**（価格に送料込み。利益計算もその前提）。サービスは日本郵便 or SpeedPAK など契約したもの
   - 発送先: まずは **米国のみ** がおすすめ
2. GitHub の Variables に追加:
   - `EXPORT_LOCATION_CITY`（例 `Yokohama`）と `EXPORT_LOCATION_PREFECTURE`（例 `Kanagawa`）— 市区町村レベルまで。番地は不要
   - `EXPORT_MERCHANT_LOCATION_KEY` = `jp-home`
3. Actions → **Japan Export Setup** → Run workflow。発送元ロケーションが作られ、配送ポリシーの一覧が表示される。
4. 1で作ったポリシーのIDを Variables の `EXPORT_FULFILLMENT_POLICY_ID` に設定。
5. Actions → **Japan Export Listing** → Run workflow（最初は `DRY_RUN=true` で候補だけ確認してもよい）。

### 調整できる値（Variables、未設定なら既定値）
- `EXPORT_LISTING_QUERIES` — 対象の検索語（`;` 区切り、既定はベイブレードX・トミカプレミアム・トミカリミテッドヴィンテージ・プラレール・たまごっち）
- `EXPORT_DAILY_LISTING_QUOTA`（既定3）、`EXPORT_UNDERCUT_USD_CENTS`（既定50＝$0.50下げ）
- `EXPORT_LISTING_SIZE`（既定 `small`）、`EXPORT_MIN_COST_RATIO`（既定0.2）

### 注意
- 新規アカウントの販売上限（例: 月50点・$700）は出品数×価格で消費される。ベイブレードX（$60前後）なら約10出品が上限。
- 「Beyblade」は海外ではHasbroの商標で、HasbroはeBayの権利者保護プログラム（VeRO）に参加している。正規の日本版タカラトミー品でも
  出品が削除されることがある。タイトルに「Japan / Takara Tomy」が入るカタログ情報を使っているが、削除されたら無理に再出品しない。
- 仕入れられない注文が出たら、早めにSeller Hubから購入者に連絡してキャンセルする（放置が最も評価に響く）。

## Pinterest (free exposure for listings)

New listings are pinned to our own Pinterest board daily by the
"Pinterest pins" workflow, each Pin linking to its eBay listing.

1. Create the app at <https://developers.pinterest.com/apps/> ("Connect app").
   Website: `https://slowjapantrails.com/`, privacy
   policy: `.../privacy.html`. Add the redirect URI
   `https://slowjapantrails.com/oauth.html` in the app
   settings.
2. Secrets: `PINTEREST_APP_ID`, `PINTEREST_APP_SECRET`, and
   `PINTEREST_TOKEN_KEY` (generate with
   `PYTHONPATH=src python scripts/pinterest_authorize.py newkey`).
   While the app only has Trial access, set the variable
   `PINTEREST_API_BASE=https://api-sandbox.pinterest.com`.
3. Open the link from `scripts/pinterest_authorize.py url`, approve, copy the
   code shown, and run the "Pinterest authorize" workflow with it.
   Pinterest rotates the refresh token on every refresh, so the token pair
   lives encrypted in `state/pinterest_token.enc` rather than in a secret.
