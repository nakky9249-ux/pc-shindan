# PC診断室

PC・パーツ・ゲーム関連ニュースをRSSから取得して表示する静的サイトです。

## 自動更新
- GitHub Actions が3時間ごとにRSS/Atomフィードを取得します。
- 記事タイトル、配信元、公開日時、短い概要、元記事リンクを `news.json` に保存します。
- `feeds.txt` に `表示名|RSS/AtomのURL` を1行ずつ追加すると、配信元を増やせます。
- GitHub Actions の「Update PC news」から「Run workflow」で手動実行できます。

## 公開設定
GitHub リポジトリの Settings → Pages で、Build and deployment の Source を「Deploy from a branch」、Branch を `main`、フォルダを `/(root)` に設定してください。

## 注意
これはRSSの自動取得・一覧表示です。AIによる記事の書き直しや独自記事の自動生成には、別途AI APIキーと追加実装が必要です。RSS配信元の利用条件を守り、全文転載はせず、元記事へのリンクを表示してください。
