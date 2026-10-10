# 公開時に行う作業

この手順の実行と本番反映は今回の範囲外です。マージの許可と本番公開の許可は分けて扱います。

## 成果物を用意する

```bash
python3 scripts/build.py
python3 -m unittest discover -s tests -v
```

配信対象は`dist/`の中身だけです。テンプレート、Gitメタデータ、テスト、ブログ編集元のJSONを直接公開しません。記事本文はビルド時に各記事ページへ生成されます。

## 公開前の確認

1. 公開する記事の内容と著者名を確認してください。既存のサンプル日記は明示されています。不要ならその記事だけを`posts.json`から外して再ビルドします。
2. メール`toyama.univ.icehockey@gmail.com`の受信と、Instagram`@toyama_angels`の運用状態を部側で確認してください。こちらからのテスト送信は行っていません。
3. 公開URLは既存の`https://ancestorbird.github.io/hockey-club-site/`を前提にしています。別のURLを使う場合は`scripts/build.py`の`BASE_URL`を変更して再ビルドしてください。
4. 共有画像は`contents/social-card.png`（1200×630）です。公開後に絶対URLで取得できることを確認してください。

## GitHub Pagesを使う場合

既存のPages設定はGitHub APIの通信制限で未確認です。リポジトリの **Settings → Pages → Build and deployment** を確認してください。

- 今回の構成ではソースのルートから配信する方法に代わり、`dist/`を配信するビルド設定が必要です。
- GitHub Actionsを使う場合、Pythonでビルドし、`actions/upload-pages-artifact`へ`path: dist`を渡した後、`actions/deploy-pages`で配信します。
- 本番を自動更新するワークフローは今回追加していません。導入は公開する段階で行ってください。
- 既存の`main`更新がPagesの公開を起動する場合、マージ前に本番反映の範囲を確認してください。

## 公開後の確認

トップ、ブログ一覧、各記事を実際の公開URLから開き、CSS・JavaScript・画像が取得できることを確認します。スマホのメニュー、検索、記事遷移、メールリンク、`sitemap.xml`も確認してください。SNS側のプレビュー表示は、HTMLの設定確認とは別に確認します。

## クラウド環境の保存

セットアップ・起動手順は環境設定のドラフトにも保存します。ドラフト保存は、現在のマシンへのネットワーク設定適用や環境のPublishを意味しません。将来のタスクで利用する場合は、環境設定で変更を確認・保存してから環境をPublishしてください。
