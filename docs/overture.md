# Overture Maps Placesを使ってみる

公式資料確認日: 2026-09-25。固定release `2026-09-23.0`、schema `v2.0.0`。

## 出典・利用条件

- [Release notes](https://docs.overturemaps.org/blog/2026/09/23/release-notes/)
- [Place schema](https://docs.overturemaps.org/schema/reference/places/place/)
- [Taxonomy](https://docs.overturemaps.org/guides/places/taxonomy-explorer/)
- [取得方法](https://docs.overturemaps.org/getting-data/)
- [ライセンス・Attribution](https://docs.overturemaps.org/attribution/)
- [Placesとソース別ライセンス](https://docs.overturemaps.org/guides/places/)

Attribution: Overture Maps Foundation, overturemaps.org (accessed 2026-09-25)。Placesはソース別にCDLA-Permissive-2.0、Apache-2.0、CC0-1.0等が適用されます。再配布時は適用ライセンス本文やNOTICE、著作権・変更表示など各条件を維持します。本実験は取得結果を再配布せず、コード・手順と集計検証結果のみを公開対象とします。リポジトリのApache-2.0によって外部データを再許諾しません。個別POIのsourcesもローカルに保存し、公開成果物追加時は条件を再確認します。

## 方針

DuckDBのhttpfs / spatialを使い公開S3のGeoParquetを匿名で読みます。token・アカウント不要。旧categoriesは使いません。公式Quickstartのcategories.primaryやtaxonomy解説のalternate表記は古いため、v2.0.0と実データを優先します。

対象はconfigs/aoi/kichijoji.tomlの矩形、境界を含みます。LIMITなし、営業状態・confidenceによる事前除外なし。住所の国コードによる除外もしません。全件とは固定データのAOI条件に合うレコード全件で、現実の全店舗の網羅を意味しません。

カフェ相当はbasic_category IN ('cafe', 'coffee_shop')。internet_cafe、動物カフェ、coffee_roastery等も公式分類に従い含みます。taxonomy.alternatesだけの一致は採用しません。Foursquareとの共通分類ではありません。


## 実行

プロジェクトルートで実行します。DuckDB 1.5.5 / Python 3.14.0で検証しました。実geometry型を検査するため、古いDuckDBでは停止する可能性があります。lockfileの環境を使ってください。

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD 'data/cache/uv'
$env:JUPYTER_CONFIG_DIR = Join-Path $PWD 'data/cache/jupyter/config'
$env:JUPYTER_DATA_DIR = Join-Path $PWD 'data/cache/jupyter/data'
$env:JUPYTER_RUNTIME_DIR = Join-Path $PWD 'data/cache/jupyter/runtime'
$env:IPYTHONDIR = Join-Path $PWD 'data/cache/ipython'
uv sync --locked --group notebooks
uv run --locked --group notebooks jupyter lab notebooks/02_overture_places.ipynb
```

公開Notebookへ出力を保存しないでください。CLI実行の場合:

```powershell
uv run --locked --group notebooks jupyter nbconvert --execute --to notebook notebooks/02_overture_places.ipynb --output 02_overture_places.executed --output-dir data/cache/overture --ExecutePreprocessor.timeout=240
uv run --locked --group notebooks jupyter nbconvert --to html data/cache/overture/02_overture_places.executed.ipynb --output-dir data/cache/overture
uv run --locked --group notebooks python -m unittest discover -s tests -v
```

オフラインテストの空間検証には、実験でインストール済みのspatial拡張を使用します。テスト自身はINSTALLやネットワークアクセスを行いません。新規環境ではNotebookの接続セルで拡張を準備してからテストしてください。

## 内部処理・測定の範囲

- `connect_overture()`はhttpfs / spatialをロードし、空の認証値のメモリ内S3設定を作ります。永続secret読み込みは無効です。`.env`やcredential chainは使いません。
- `fetch_overture_places()`は固定S3パスをread_parquetで読み、bbox重なり条件で候補抽出後、ST_X / ST_Yで境界を含む厳密な矩形判定を行います。bboxの丸めによる候補の取りこぼしを避けます。180秒の締切を超えた場合は停止し、途中結果を全件とは扱いません。
- NULL・非Point geometry、ID重複、geometryとbboxの整合性を検査します。ただしbboxがNULL/不正で候補に入らない行まで全世界走査して検証してはいません。
- `filter_overture_cafes()`は取得結果だけをbasic_categoryで選びます。実行後のDataFrame編集は内部テーブルには反映されません。
- `summarize_overture()`は全カテゴリ件数、カフェ内taxonomy.primary内訳、NULL件数、状態、confidence分位点、sources件数を返します。
- `save_overture_results()`はdata/raw/overture配下にGeoParquetとmanifestを保存します。releaseとschema versionを別項目にし、UTC時刻、AOI、SQL、環境、ソース・出力SHA-256、出力サイズを記録します。

EXPLAINのREAD_PARQUET配下のFiltersはpredicate pushdownの計画上の確認です。推定行数を実スキャン量と解釈しません。通信バイト数、スキャンバイト数、ピークメモリはこの実装では未測定で、manifestにはnullを記録します。保存ファイルサイズや経過時間から逆算しません。1GBはDuckDB設定上限であり、測定ピークでもプロセス全体の厳密な上限でもありません。

## STAC・CLI・taxonomy資料

調査時STAC 1.1.0のlatestは2026-09-23.0でしたが、本実験はlatestを解決しません。STACやPython CLIを主経路には使用せず、固定S3パスで取得します。[Python client](https://docs.overturemaps.org/getting-data/overturemaps-py/)はbbox・ストリーミング・STAC利用に対応しています。

- [固定release STAC](https://stac.overturemaps.org/2026-09-23.0/catalog.json)
- [固定taxonomy CSV](https://docs.overturemaps.org/taxonomy/2026-09-23.0/taxonomy.csv)
- [固定basic categories CSV](https://docs.overturemaps.org/taxonomy/2026-09-23.0/basic_categories.csv)

confidenceは提供元の存在への確信度スコアです。校正された確率や独自の品質指標とはみなしません。operating_statusは営業時間内かどうかを意味しません。NULLを営業中と解釈しません。
