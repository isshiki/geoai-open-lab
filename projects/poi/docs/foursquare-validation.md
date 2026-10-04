# Foursquare最小実験の検証記録

確認日: **2026-09-24**。初心者向けに整理したNotebookの **全6コードセルが成功** しました。下記に最新の再検証と、リファクタ前の実測記録を残します。

## 初心者向けリファクタ後の再検証

- 公開Notebookのコードを **225行から15行** に整理。目的・準備・接続・吉祥寺POI取得・カテゴリ抽出・結果の6章と、6コードセルにしました。
- snapshot固定、スキーマ検証、AOI・国・POI重複の検査、カテゴリ辞書整合性と不一致確認を `src/geoai_open_lab/foursquare.py` に移しました。manifest生成は `_foursquare_provenance.py` に分離しています。
- 最終再実行: `2026-09-24T08:15:07.024556+00:00` ～ `2026-09-24T08:15:54.227380+00:00`。
- 最新manifest: `data/raw/foursquare/20260924T081554Z-e3a38612/manifest.json`。
- 下記の同じ2つのsnapshot IDを再使用。**POIサンプル500件、その中のカフェ・コーヒーショップ37件**、上限到達、その他の検査結果はリファクタ前と一致しました。地域全体のPOI数・店舗数ではありません。
- `places.json` / `categories.json` / `cafes.json` のSHA-256がリファクタ前とすべて一致しました。表示用のpandas DataFrame導入で抽出結果が変わっていないことも確認できました。
- オフラインテスト **19件成功**。既存の安全性・抽出検証に加え、保存済みsnapshotの再使用・失効時の停止、schema変更、POI重複、DataFrame変更、取得し直した際の古い抽出結果の破棄、manifestのチェック項目と出力ハッシュ・秘密情報非保存を検証しました。
- 公開Notebookはoutput / execution count / attachmentsなし。実行結果は `data/cache/foursquare/01_foursquare_places.executed.ipynb` と同名HTMLに保存しました。HTMLの目視検査は既述のブラウザ制限により未実施です。
- Notebookに長いSQLや検証辞書を表示せず、POI表5行・カフェ表10行とサンプル件数を表示します。詳細なルールと関数の役割は[利用ガイド](foursquare.md#初心者向けnotebookと内部処理)で説明しています。

## リファクタ前の実行と再現情報

- 取得開始（UTC）: `2026-09-24T07:52:01.623739+00:00`
- 取得完了（UTC）: `2026-09-24T07:52:51.252745+00:00`
- Python: `3.14.0` / DuckDB: `1.5.5`
- 拡張: `httpfs: 827222f`、`iceberg: 45163a28`
- AOI: `configs/aoi/kichijoji.toml`。WGS84、西139.574、南35.699、東139.586、北35.708（境界を含む）。筆者定義の実験用矩形です。
- ローカルmanifest: `data/raw/foursquare/20260924T075201Z-9cce1e09/manifest.json`
- 認証: `.env` の `FSQ_OS_PLACES_TOKEN`。`FSQ_API_KEY` は未使用。

| データ | snapshot ID | snapshot日時（DuckDBのtimestamp_ms表示） |
| --- | --- | --- |
| Places | `2325979374271449319` | `2026-09-15 20:07:45.157000` |
| Categories | `5006175908264532092` | `2026-09-15 19:57:45.096000` |

日時はDuckDBから返された表記をそのまま記録しています。月次release名との対応は未特定です。初回に選んだIDをローカルpinsファイルから再使用し、最終実行でも同じsnapshotを読みました。別環境では `connect_foursquare(snapshot_ids={"places": "2325979374271449319", "categories": "5006175908264532092"})` と指定できます。履歴が提供元で削除された場合は再取得できない可能性があります。

## 実測結果

国コードJPとbboxで絞り、ID順の先頭500件を保存しました。上限判定用の501件目が返ったため **truncated = true** です。以下のPOI件数はすべて取得した500件の中の値であり、AOI全体・日本全体の件数ではありません。

| 確認項目 | 結果 |
| --- | ---: |
| 保存した日本POI | 500 |
| カフェ・コーヒーショップ | 37 |
| date_closedが入っているPOI | 109 |
| date_closedがNULLのPOI | 391 |
| カテゴリIDが空またはNULLのPOI | 29 |
| Categories辞書の件数 | 1279 |
| POIに付いているが辞書に未対応のカテゴリID | 0 |

カフェ抽出はカテゴリ名 `Café` と `Coffee Shop` の完全一致で親候補を選び、子カテゴリも含めてIDで照合しています。店名からは推定していません。複数カテゴリでもPOIを重複計上しない `EXISTS` を使いました。閉店日は除外条件にしていないため、37件を現在営業中の店舗数とは解釈できません。date_closedがNULLであることも営業中の保証ではありません。

## 実行して分かったこと

1. **テーブル一覧が空でも直接参照できた。** `information_schema.tables`、`SHOW ALL TABLES`、`SHOW TABLES FROM places.datasets` は空でした。一方、公式名 `places.datasets.places_os` と `places.datasets.categories_os` のDESCRIBE・読取は成功しました。一覧が空という理由だけで処理を止める実装を修正しました。他のテーブルを網羅的に列挙できたわけではありません。
2. **実際のカテゴリIDは配列だった。** Portal画面のSTRING表示とは異なり、DuckDBでは `fsq_category_ids` が `VARCHAR[]` でした。Placesは27列、Categoriesは16列です。日付列はVARCHARとして返りました。
3. **カフェの部分一致は広すぎた。** 最初の `cafe / café / coffee shop` 部分一致はCafeteriaなども候補に含めました。最終版はCafé / Coffee Shopへの完全一致と子カテゴリに限定しています。広い定義で得た初回の値と最終結果を混ぜないでください。
4. **小さなAOIでも500件の上限に達した。** 全件数・網羅性の評価には追加の設計が必要です。今回のID順サンプルには無作為性・代表性を仮定しません。

公式の取得方法・ライセンス・NOTICEは [利用手順](foursquare.md#公式仕様と利用条件) に出典を記録しています。

## 初回検証と公開安全性

- オフラインテスト11件が成功。認証変数の区別、秘密情報を含む例外の抑制、snapshot入力、bbox・国、カテゴリJOIN・子カテゴリ・重複排除、上限時の件数表示、重複辞書の拒否、空のカタログ一覧への対応を検証しました。テストデータは架空です。
- 最終Notebookを上から全セル実行し、実データの範囲・国コード・ID重複・辞書JOINの検査も成功しました。
- 生データ、実行済みNotebook、詳細manifestはGit管理外の `data/` にのみ保存。公開用Notebookの出力・実行番号・添付データは空です。
- 公開候補ファイルに設定済みのAPIキー・Portal tokenが含まれないことを検査しました。
- 最新の実行済みNotebookとHTMLは `data/cache/foursquare/` に保存。HTMLの目視検査はブラウザのローカルURL制限により未実施です。

## 再実行

[実行手順](foursquare.md#準備)に従い、カーネルを再起動して上から実行してください。保存済みsnapshot IDを再使用します。公開用Notebookへ出力を保存しないでください。

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD 'data/cache/uv'
uv run --locked --group notebooks python -m unittest discover -s tests -v
```

今回の観測を第2回記事の材料にできます。Overture / OSM比較、網羅性評価、名寄せ、Embedding、機械学習は実施していません。
