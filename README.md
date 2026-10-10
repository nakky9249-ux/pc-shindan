# PC診断室

PC・パーツ・ゲーム関連ニュースをRSSから自動取得し、検索できる一覧として表示する静的サイトです。

## 自動更新
- GitHub Actions が3時間ごとにRSS/Atomフィードを取得します。
- 記事タイトル、配信元、公開日時、概要、元記事リンクを `news.json` に保存します。
- 取得前にRSSパーサーのユニットテストを実行します。
- `feeds.txt` に `表示名|RSS/AtomのURL` を追加すると配信元を増やせます。
- GitHub Actions の「Update PC news」から「Run workflow」で手動実行できます。

## GitHub Pages
リポジトリの Settings → Pages で Source を「Deploy from a branch」、Branch を `main`、フォルダを `/(root)` に設定してください。

## 注意
RSSの見出し・概要・リンクを利用する仕組みです。記事本文の全文転載はしません。AIによる独自記事の生成・要約には別途AI APIと実装が必要です。RSS配信元の利用条件を守ってください。


## パーツ価格の自動取得（楽天市場）
パーツ価格は、楽天ウェブサービスの公式「楽天市場商品検索API」から候補商品を取得し、GitHub Actionsで約6時間ごとに `prices.json` へ保存する構成です。APIキーを登録するまでは価格自動取得は動作せず、参考価格が表示されます。

### 初回設定
1. [楽天ウェブサービス](https://webservice.rakuten.co.jp/) に楽天アカウントでログインし、アプリを登録して「アプリID」と「アクセスキー」を取得します。
2. GitHubのこのリポジトリで Settings → Secrets and variables → Actions → New repository secret を開きます。
3. 次の2つを登録します。
   - `RAKUTEN_APP_ID`：楽天APIのアプリID
   - `RAKUTEN_ACCESS_KEY`：楽天APIのアクセスキー
4. Actions →「Update PC part prices」→「Run workflow」で初回実行します。
5. 成功後、`prices.json` が更新され、サイトに価格データと最終更新日時が表示されます。

APIキーをHTMLやJavaScriptに直接書かないでください。GitHub Actions Secretsに保管します。取得できる価格は楽天市場の検索結果に含まれる候補商品の価格であり、全ショップの最安値やBTOショップ価格を保証しません。価格・送料・在庫・型番・新品/中古の別を購入前に確認してください。
