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
