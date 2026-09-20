# eBay-automation

## Printify: 自社ブランド「EQUINOX」の T シャツ・ステッカー作成

ブランド名は **EQUINOX**(春分)。Aries(牡羊座)のシーズンが春分から始まることにちなんでいます。

このリポジトリには、Aries ラムのライン アート([`assets/designs/aries-ram-lineart.jpg`](assets/designs/aries-ram-lineart.jpg))を使って
Printify 上に T シャツ・ステッカーの商品を自動作成するスクリプトが入っています。印刷には白背景を除去した透過 PNG
([`assets/designs/aries-ram-lineart-transparent.png`](assets/designs/aries-ram-lineart-transparent.png))を使用します。
作成される商品は次の 3 つです。

- EQUINOX - Aries Ram Left Chest T-Shirt(左胸ワンポイント)
- EQUINOX - Aries Ram Sleeve T-Shirt(左袖ワンポイント、デザイン違いとして別商品)
- EQUINOX - Aries Ram Sticker(ダイカット/型抜きステッカー、公開済み)

Printify にはショップ名(ブランド名)を API から変更する仕組みがないため、ショップ名自体
(現在は作成時の「Aries」)を変更したい場合は Printify ダッシュボードで手動リネームが必要です。

### できること / できないこと

Printify には「ブランド(ショップ)を API だけで新規作成する」エンドポイントはありません。
ショップ接続は **Printify ダッシュボード上で一度だけ手動** で行う必要があります(ログイン中の Printify
アカウントに対する操作のため、この環境からは代行できません)。それ以降の

- 画像アップロード
- T シャツ・ステッカー商品の作成(カタログから最適な blueprint / print provider を自動選択)
- (任意で)商品の公開

はこのスクリプトが自動で行います。

### 事前準備(手動・1 回だけ)

1. Printify アカウントを作成し、ログインする。
2. ダッシュボードで **Add new store** からストア接続を作成する。
   - 実店舗(Etsy/Shopify 等)と連携しない場合は「Printify API」(手動/API 専用ストア)を選択すれば OK。
   - これが今回の「自社ブランド」の受け皿(ショップ)になります。
3. **Account settings → Connections** で Personal Access Token を発行する。
4. 作成したショップの `shop_id` を控える(トークン発行後に `GET https://api.printify.com/v1/shops.json` を叩くと一覧取得できます)。

### セットアップ

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env を編集して PRINTIFY_API_TOKEN / PRINTIFY_SHOP_ID を設定
```

### 実行

```bash
python -m printify.create_brand_products --brand-name "あなたのブランド名"
```

- デフォルトでは商品は **下書き(未公開)** として作成されます。Printify ダッシュボードでモックアップを確認してから、
  問題なければ `--publish` を付けて再実行すると公開されます。
- 実行結果(アップロード画像 ID・作成した商品 ID など)は `printify/last_run.json` に書き出されます。
- Blueprint(商品テンプレート)は既定でキーワード検索(`Unisex Heavy Cotton Tee` / `Kiss-Cut Stickers`)により
  カタログから自動選択します。特定の blueprint / print provider を固定したい場合は `.env` の
  `TSHIRT_BLUEPRINT_ID` などを指定してください。
- 既に作成済みの商品を作り直さず更新したい場合は、`.env` の `TSHIRT_CHEST_PRODUCT_ID` /
  `TSHIRT_SLEEVE_PRODUCT_ID` / `STICKER_PRODUCT_ID` に商品 ID(`printify/last_run.json` に出力されます)を
  設定してから再実行してください。デザイン差し替えや配置調整のたびに毎回新しい商品を作らずに済みます。
- 袖プリントの向きは `TSHIRT_SLEEVE_POSITION`(既定は `left_sleeve`、`right_sleeve` にも変更可)で指定します。

### 画像について

`assets/designs/aries-ram-lineart.jpg` はオリジナルの JPEG(白背景・1258×1304px)です。印刷にはこれを
透過 PNG 化した [`assets/designs/aries-ram-lineart-transparent.png`](assets/designs/aries-ram-lineart-transparent.png)
を使用しています(生成コマンド: `python -m printify.prepare_design assets/designs/aries-ram-lineart.jpg assets/designs/aries-ram-lineart-transparent.png`)。
背景の淡いグレーを検出して透過にし、白に近いほど透明・黒に近いほど不透明になる境界をなだらかにぼかしているため、
ステッカーのダイカット(型抜き)やシャツの生地色がそのまま背景として活きます。

ステッカーや胸・袖ワンポイント程度のサイズであれば解像度は十分ですが、背中いっぱいの大判プリントなど大きな
印刷面積で使う場合は、Printify 側で低解像度警告が出ることがあります。より高解像度の元データがあれば差し替えてください。

`assets/reference/aries-ram-tattoo-reference.jpg` はデザインの参照用(タトゥー写真)であり、印刷用データとしては
使用していません。

## eBay: Printify 商品の出品

`ebay/` に、Printify で作った商品(EQUINOX の T シャツ・ステッカー)を eBay に多バリエーション出品として
連携するスクリプトが入っています。Printify と違い、eBay 側は以下の理由で **完全な無人セットアップができません**。

- API キー発行に加えて、**ブラウザでの eBay ログイン + 同意操作**(OAuth)が必要(この環境から代行不可)。
- 出品には配送方法・支払い・返品ポリシーと発送元住所が必須で、これらは実際のビジネス情報のため代わりに
  決められません。

### 事前準備(手動)

1. [developer.ebay.com](https://developer.ebay.com/) で Developer アカウントを作成し、**Application Keys** ページで
   キーセット(Client ID / Client Secret)を発行する。最初は Sandbox キーでのテストを推奨。
2. 同じページで **RuName**(OAuth のリダイレクト先識別子)を作成する。
3. `.env` に `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` / `EBAY_RU_NAME` / `EBAY_SANDBOX` を設定する。

### OAuth 同意(手動・1 回だけ)

```bash
python -m ebay.oauth_consent
# 表示された URL をブラウザで開き、eBay セラーアカウントでログインして許可する
# リダイレクト先 URL の ?code=... の値をコピーする
python -m ebay.exchange_code "<コピーした code>"
# 出力された refresh_token を .env の EBAY_REFRESH_TOKEN に保存する
```

`EBAY_REFRESH_TOKEN` は約 18 ヶ月有効で、以降のスクリプトはこれを使って自動でアクセストークンを更新します。

### アカウント初期設定(発送元ロケーション・出品ポリシー)

`.env` に実際の発送元住所とポリシー条件(ハンドリング日数・送料・返品条件など)を入力してから:

```bash
python -m ebay.setup_account
```

既存の同名ロケーション/ポリシーがあればそれを再利用し、なければ作成します。アカウントに既に同じ
カテゴリ/マーケットプレイス向けの支払い・返品ポリシーがある場合(`Duplicate Policy`)は、そちらを自動で
再利用します。出力された ID を `.env` の `EBAY_MERCHANT_LOCATION_KEY` / `EBAY_FULFILLMENT_POLICY_ID` /
`EBAY_PAYMENT_POLICY_ID` / `EBAY_RETURN_POLICY_ID` に設定してください。

**配送ポリシーについて**: eBay の仕様上、発送元が海外(例: 日本)でも `DOMESTIC` の配送オプションが
1つ必須です(`SHIPELIG_ERROR_CODE_NAME: DOMESTIC_SHIPPING_REQUIRED`)。実際には使われない前提のダミー
として `EBAY_DOMESTIC_SHIPPING_*` を設定し、実際に使う海外発送は `EBAY_INTERNATIONAL_SHIPPING_SERVICE`
(既定: `StandardInternational`、eBay 側で自動的に `shippingCarrierCode=GENERIC` が割り当てられる、
特定キャリア非依存の国際配送クラス)側で設定します。配送キャリア/サービスコードは REST API から一覧取得
できないため(Metadata API に該当エンドポイントなし)、レガシー Trading API の `GeteBayDetails`
(`DetailName=ShippingServiceDetails`)で実在するコードを確認して使っています。

### 出品実行

```bash
python -m ebay.sync_from_printify <Printify商品ID> --sku-prefix EQX-CHEST --category-query "T-Shirt"
# 内容を確認できたら --publish を付けて再実行すると eBay に公開されます
```

Printify 商品の各バリエーション(色・サイズ)ごとに eBay の inventory item を作成し、1 つの
inventory item group にまとめて多バリエーション出品として公開します。eBay の商品カテゴリは
`--category-query` のキーワードからカタログ(Taxonomy API)を検索して自動選択します(`--category-id` で固定も可能)。

### ファイル構成

```
printify/
  client.py                 Printify REST API の薄いラッパー
  catalog.py                blueprint / print provider / variant の自動選択ロジック
  create_brand_products.py  T シャツ・ステッカーを作成/更新するメインスクリプト (CLI)
  prepare_design.py         白背景を透過 PNG に変換するユーティリティ
ebay/
  client.py                 eBay REST API(OAuth・Taxonomy・Account・Inventory)の薄いラッパー
  oauth_consent.py          OAuth 同意 URL を表示(ブラウザでの手動承認が必要)
  exchange_code.py          認可コードを refresh_token に交換
  setup_account.py          発送元ロケーション・出品ポリシーの作成/再利用
  sync_from_printify.py     Printify 商品を eBay に多バリエーション出品するメインスクリプト (CLI)
assets/
  designs/                  印刷に使うデザインデータ
  reference/                参考画像(印刷には使わない)
```
