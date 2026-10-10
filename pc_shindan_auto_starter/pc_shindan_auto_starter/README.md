# PC診断室：無料RSS自動更新スターター

## このセットでできること
- `feeds.txt` に登録したRSS/Atomの見出し・リンク・日付を取得
- `news.json` を自動生成
- GitHub Actionsで毎日定期実行
- `index.html` の「最新PCニュース」に記事リンクを表示

## 重要
この段階ではAIによる記事本文の自動生成はしません。まずは無料で安定した情報収集を作ります。
見出しや要約を掲載するときは、元記事へのリンクを付け、事実確認をしてください。
RSS配信元の利用規約・再掲載条件を確認してください。記事本文や画像を無断転載しないでください。
`feeds.txt` にRSS/AtomのURLを登録するまではニュースは取得されません。

## 手順
1. GitHubで新しい **Public** リポジトリを作る（公開するHTMLに個人情報を含めない）。
2. このフォルダ内のファイルをすべてリポジトリにアップロードする。`.github/workflows/update-news.yml` も含める。
3. RSS/Atomを配信する公式サイトを選び、配信元の利用条件を確認して `feeds.txt` に次の形式で追加する：
   `表示名|https://実際のRSSフィードURL`
4. `news.json` が `[]` のままでも問題ありません。最初の自動実行後に記事が入ります。
5. GitHubリポジトリの **Actions** タブを開き、`Update PC news` を選び、**Run workflow** で初回テスト。
6. 成功したら **Settings → Pages** で `Deploy from a branch`、ブランチ `main`、フォルダ `/ (root)` を選んで公開。
7. 公開URLでニュース欄を確認。反映に数分かかることがあります。

## ローカルテスト（任意）
Python 3がある場合、フォルダ内で次を実行：
`python scripts/fetch_news.py`
成功すると `news.json` が更新されます。

## 無料枠について
GitHubの機能・利用条件は変更されることがあります。Actionsの利用上限やリポジトリ設定を確認してください。
