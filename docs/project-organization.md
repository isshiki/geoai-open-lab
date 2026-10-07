# 目的別プロジェクトへの整理と記事連携の計画

2026-10-04作成。**承認済み・ローカル移行検証済み**。POIの配置変更を実施した。他チャットへの送信・ブログ変更は行っていない。

## 目的ごとにコード・文書・Notebookをまとめる

リポジトリ全体の連番を記事シリーズの番号として扱わない。POI編は進行中の独立したシリーズ、駅の縄張りは別テーマとする。「実験05」「実験06」という名称を新テーマへ引き継がない。Notebook番号は各プロジェクト内の実行順序で、ブログの記事番号とは独立させる。

```text
geoai-open-lab/
├─ AGENTS.md                     # 全プロジェクトへ適用
├─ LICENSE
├─ README.md                     # テーマ別の入口
├─ .gitignore
├─ docs/
│  ├─ data-policy.md             # 全体共通の公開安全性・データ方針
│  └─ project-organization.md    # 構成と記事連携の共通方針
└─ projects/
   ├─ poi/
   │  ├─ README.md
   │  ├─ pyproject.toml / uv.lock
   │  ├─ .env.example
   │  ├─ notebooks/             # 既存01〜04の順序・内容を維持
   │  ├─ docs/                  # 取得手順・検証・記事引き継ぎ
   │  ├─ src/geoai_open_lab/    # 既存のimport名・公開APIを維持
   │  ├─ tests/
   │  ├─ configs/
   │  └─ data/                  # Git管理外
   └─ station-territory/
      ├─ README.md
      ├─ pyproject.toml / uv.lock
      ├─ notebooks/01_rankings.ipynb
      ├─ docs/                  # 定義・出典・検証・記事引き継ぎ
      ├─ src/station_territory/
      ├─ tests/
      ├─ configs/
      └─ data/                  # Git管理外
```

各プロジェクトに独立したuv環境・lockfileを持たせる。初回はuv workspaceや共通utilityパッケージを作らない。駅の分析の依存追加によってPOI編の環境を更新しない。元の依頼にあるルートsrc/geoai_open_lab/への追加は、目的別分離の後のユーザー指示に合わせ、駅側専用src/station_territory/への配置へ変更する。

Apache-2.0のコードと第三者データのライセンスは区別する。パッケージをビルドする際のLICENSE同梱も確認する。取得物・図表・HTML・実行済みNotebook・詳細manifestは各project/data/へ置く。現在の `/data/` の除外指定だけではネスト先を覆わないため、移動前に `/projects/*/data/` を明示的に除外し、git check-ignoreで確認する。

旧高齢化調査のローカル保管物・取得データは変更しない。新テーマの結果を旧計画・閾値へ反映しない。既存データの移動やコピーは別途パスとhashを記録し、ファイル整理のためにデータを再取得しない。

## 段階的な移行

1. 本計画と[駅の縄張り移行計画](../projects/station-territory/docs/migration-plan.md)をレビューする。
2. POI記事のChatGPTチャット・ブログ側Codexと、利用中のNotebook/doc URL、原稿の状況、変更可能な公開リンクを照合する。現時点では両者のチャット・ブログリポジトリ・記事URLは未特定。
3. POIの配置変更を一つの変更として行う。Notebook4本、docs8本、src・tests・configs・環境定義を移す。README、Notebook内リンク、実行コマンド、manifestのコードパス、テストのfixtureパス、ルート判定を同時更新する。解析条件・カテゴリ定義・snapshotは変更しない。
4. 旧URLはGitHubが自動転送すると仮定しない。旧→新URL表を作り、ブログ側のリンク更新に合わせて切り替える。更新できない既存リンクがあれば、旧パスには計算コードを持たない移動案内を一時的に残す。実装を二重管理しない。
5. POI全テスト（移行後65件）と移動に影響するNotebookの実行を確認する。保存済みデータを優先し、ネットワーク取得が必要な場合は実行前に条件を提示する。履歴付きmanifestの古いパス・hashは書き換えず、新しい実行記録を追加する。
6. 駅の縄張りの分析を専用projectで移植・再検証する。POIの移動と分析結果の変更は分離してレビューする。

既存rootの `.env` は表示・コピー・移動しない。POI移行時は互換的なローカル読み込み方法を明示し、Notebook出力・manifestに値を残さない。現状のdata/はそのまま保全し、新配置へ必要なデータを取り込む際は読取元・保存先・サイズ・hashを記録する。環境・入力の切替確認前に旧パスを削除しない。

## 3者の役割と受け渡し

| 担当 | 管理するもの | 次の担当へ渡すもの |
| --- | --- | --- |
| GeoAIラボのCodex | 計算仕様、入力、コード、テスト、再実行、検証と限界 | 根拠付きの執筆資料、承認した図表、Notebook/docのURL |
| POI記事のChatGPTチャット | 読者像、記事構成、説明、シリーズの順番 | 原稿、必要な追加説明・図表の依頼、利用するリンク一覧 |
| ブログサイトのCodex | 原稿のサイト組込み、画像配置、出典、リンク、表示 | プレビュー、リンク確認結果、公開URL、使用した資料の版 |

新しい駅の記事も同じ受け渡し方式を使うが、POIシリーズの原稿とは別に扱う。原稿側で数値・集計条件を変える必要が出た場合はラボへ戻し、文章だけで分析定義を変更しない。

各project/docs/article-handoff.mdを受け渡しの入口にする。次を短く記録する：テーマID、記事の状態、根拠のcommitと実行ID、採用する指標・言えること・言えないこと、図表のファイル名/hash・出典、利用するGitHub URL、未検証事項、旧→新URL対応、原稿担当・サイト担当の確認状態。実データや秘密情報は添付しない。生成図表と表の実体はGit管理外で管理し、ブログへ渡すものを選んで公開条件を確認する。

他チャットへの自動送信やブログの変更・公開はこの計画では行わない。共有先が確定するまでは、ユーザーが渡せる資料として用意する。pushは毎回ユーザー確認後。分析データ・依存パッケージ・拡張機能など新規ダウンロードが必要なら、取得前にファイル名・URL・サイズ（不明ならその旨）を提示して確認する。

## 今回の到達点

- POIコード・Notebook・文書・環境をprojects/poiへ移動済み。旧Notebook/docには移動案内を残す。
- 駅テーマは別パッケージへ移行し、東京の道路再生成と格子以降の集計を検証済み。元のeki-walk/rail-gap-mapは編集しない。
- ブログ側の反映を確認していない段階で「新URLへ移行完了」「記事掲載準備完了」としない。

## 将来テーマの登録（2026-10-07）

[retail-spatial-models](../projects/retail-spatial-models/README.md)を、POI・駅の縄張りとは独立した研究候補として追加した。現在の構成はREADMEとdocsの計画・出典確認のみ。上の構成図は実装済み2テーマの移行時点を示す。新テーマの環境・コード・Notebookは実装着手時に追加し、計画登録だけでデータ取得や分析を始めない。詳細は[研究計画](../projects/retail-spatial-models/docs/research-plan.md)を参照。

## 図版の署名と出典

ユーザー指定の署名は [masahiko.info](https://masahiko.info/)。図版のタイトルと同じ高さの右上へ `masahiko.info` を13ptのグレーで配置する。内容や凡例に重ねず、データ提供者のAttributionは別に読める大きさで記載する。SVG/HTML等でリンクを付けられる場合は https://masahiko.info/ を使用する。署名は出典・ライセンス表示の代わりにはしない。

検証結果は [駅テーマの検証記録](../projects/station-territory/docs/validation.md) を参照。POI 65テスト、駅テーマ14テストが通過。OSM・POI比較・駅ランキングのNotebookをカーネル実行。HTMLのブラウザ目視はfile URL制限により未検証。公開の状態はGitHubのmainを参照。
