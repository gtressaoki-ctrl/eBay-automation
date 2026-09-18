# eBay-automation

## Printify: 自社ブランドの T シャツ・ステッカー作成

このリポジトリには、Aries(牡羊座)ラムのライン アート([`assets/designs/aries-ram-lineart.jpg`](assets/designs/aries-ram-lineart.jpg))を使って
Printify 上に T シャツとステッカーの商品を自動作成するスクリプトが入っています。

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
- Blueprint(商品テンプレート)は既定でキーワード検索(`Unisex Heavy Cotton Tee` / `Kiss Cut Stickers`)により
  カタログから自動選択します。特定の blueprint / print provider を固定したい場合は `.env` の
  `TSHIRT_BLUEPRINT_ID` などを指定してください。

### 画像について

`assets/designs/aries-ram-lineart.jpg` は 1258×1304px です。ステッカーや胸ワンポイント程度のサイズであれば
問題ありませんが、背中いっぱいの大判プリントなど大きな印刷面積で使う場合は、Printify 側で低解像度警告が出ることが
あります。より高解像度の元データがあれば差し替えてください。

`assets/reference/aries-ram-tattoo-reference.jpg` はデザインの参照用(タトゥー写真)であり、印刷用データとしては
使用していません。

### ファイル構成

```
printify/
  client.py                 Printify REST API の薄いラッパー
  catalog.py                blueprint / print provider / variant の自動選択ロジック
  create_brand_products.py  T シャツ・ステッカーを作成するメインスクリプト (CLI)
assets/
  designs/                  印刷に使うデザインデータ
  reference/                参考画像(印刷には使わない)
```
