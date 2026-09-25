# Foursquare Open Source Placesを使ってみる

公式仕様の確認日: **2026-09-24**。この実験はOS Places / OS Categoriesのみを対象とします。商用のPro / Premiumサンプルや会社資産は利用しません。

## 公式仕様と利用条件

- [Access FSQ OS Places](https://docs.foursquare.com/data-products/docs/access-fsq-os-places): 現在の配布はPlaces PortalのIcebergカタログ。旧公開S3の月次Parquetを前提にしません。
- [Portal: OS Places / DuckDB](https://places.foursquare.com/dataset/OS%20Places/code): warehouseは `places`、endpointは `https://catalog.h3-hub.foursquare.com/iceberg`、テーブルは `places.datasets.places_os`。
- [Portal: OS Categories](https://places.foursquare.com/dataset/OS%20Categories/code): テーブルは `places.datasets.categories_os`。両Portalページをログイン前の公開画面で確認しました。
- [公式スキーマ](https://docs.foursquare.com/data-products/docs/places-os-data-schema): 座標はWGS84、国コードは2桁、POIのカテゴリIDは配列、Categoriesは階層付き辞書です。
- [公式リリースノート](https://docs.foursquare.com/data-products/docs/fsq-os-places-release-notes): September 2026の記載を確認。ただし、この見出しを実際に読み取ったsnapshotの版として代用しません。
- [DuckDB Iceberg](https://duckdb.org/docs/stable/core_extensions/iceberg/overview): `iceberg_snapshots` と `AT (VERSION => ...)` を使用します。

Foursquare提供のOSデータは [公式のApache 2.0表示](https://docs.foursquare.com/data-products/docs/fsq-places-open-source) と [Foursquare OS Places NOTICE](https://opensource.foursquare.com/places-notice-txt/) に従います。PortalのOS Categoriesも同じNOTICEを案内しています。本リポジトリのライセンスによって外部データを再許諾するものではありません。

Attribution: **Foursquare OS Places / OS Categories — Foursquare Labs, Inc.** 提供元のNOTICEは2026年の著作権表示、ライセンスの同梱、変更表示、NOTICE全文の保持を求めています。フラットファイルの再配布では元NOTICE全文・ライセンス・変更内容を添付し、API形式では開発者文書へのNOTICE掲載が案内されています。抽出・加工しても元の表示条件を維持します。今回、生データ・Categories・抽出結果の再配布は行わず、Git管理外にのみ保存します。集計・地図・Embeddingの公開は、この実験から包括的に許諾済みとは扱わず、後続の成果物ごとに条件を再確認します。

## 準備

1. 個人用アカウントで [Places Portal](https://places.foursquare.com/) にログインします。
2. OS Placesの **Access Data** でPortal access tokenを発行します。Places APIのAPIキーとは区別してください。アカウント登録・規約同意は利用者が行います。
3. リポジトリ直下の `.env.example` を `.env` にコピーし、エディタで `FSQ_OS_PLACES_TOKEN=` の右側にtokenを保存します。既存の `.env` は上書きしないでください。
4. tokenや接続SQLをチャット・Notebookセル・シェル履歴へ貼らないでください。

`FSQ_API_KEY` はPlaces API用に分けて保持します。このNotebookは `FSQ_OS_PLACES_TOKEN` のみを参照し、APIキーへの代替や旧 `FSQ_TOKEN` の参照は行いません。

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD 'data/cache/uv'
$env:JUPYTER_CONFIG_DIR = Join-Path $PWD 'data/cache/jupyter/config'
$env:JUPYTER_DATA_DIR = Join-Path $PWD 'data/cache/jupyter/data'
$env:JUPYTER_RUNTIME_DIR = Join-Path $PWD 'data/cache/jupyter/runtime'
$env:IPYTHONDIR = Join-Path $PWD 'data/cache/ipython'
uv sync --locked --group notebooks
uv run --locked --group notebooks jupyter lab notebooks/01_foursquare_places.ipynb
```

ブラウザでPython 3カーネルを選び、上から順に実行します。CLIで実行する場合は、公開用Notebookを上書きせず、結果を `data/cache/` に出します。

```powershell
uv run --locked --group notebooks jupyter nbconvert --execute --to notebook notebooks/01_foursquare_places.ipynb --output 01_foursquare_places.executed --output-dir data/cache --ExecutePreprocessor.timeout=300
```

初回は公式 `httpfs` / `iceberg` 拡張を取得します。保存先は `data/cache/duckdb/` です。カタログはread-onlyで接続し、tokenはメモリ内secretに限定します。`.env` は平文のローカルファイルです。OSのアクセス権を保ち、公開・共有しないでください。Notebookはtokenを返さず、リモート例外本文も抑制します。ログやHTTPデバッグを有効にしないでください。

## 初心者向けNotebookと内部処理

Notebookの目的は「接続 → 吉祥寺POI取得 → カフェ抽出」の動作確認です。長いSQL、スキーマ・snapshotの一覧、検証辞書、manifestの組み立ては表示せず、少量の表とサンプル件数を表示します。

```python
from geoai_open_lab.foursquare import (
    connect_foursquare, load_aoi, fetch_places,
    filter_places_by_category, save_results,
)

con = connect_foursquare()
kichijoji = load_aoi("configs/aoi/kichijoji.toml")
places = fetch_places(con, bbox=kichijoji, country="JP", limit=500)
cafes = filter_places_by_category(con, places, categories=["Cafe", "Coffee Shop"])
result_dir = save_results(con)
con.close()
```

`places` と `cafes` はpandasのDataFrameです。`head()`で少量の行を見られます。ブログではtoken準備と上の接続・取得・抽出を中心に説明できます。

| 関数 | 内部で行うこと |
| --- | --- |
| `connect_foursquare()` | プロジェクトのtokenを読み、httpfs / icebergをLOAD。一時secretでread-onlyカタログをATTACH。Places / Categoriesのsnapshotを個別に固定し、固定版のschemaを検証 |
| `load_aoi()` | 既存の共有TOMLからWGS84の対象地域を読み込む。国コードと座標範囲も検査 |
| `fetch_places()` | 国・bboxで絞り、上限+1件で打ち切りを検出。POI IDの重複・NULL、AOI・国を検査。表と内部記録を作る |
| `filter_places_by_category()` | 固定版Categoriesを取得。件数上限、辞書IDの重複・NULL、POIカテゴリIDとの不一致を検査。名称の完全一致と階層IDで照合し、EXISTSでPOI重複を防ぐ |
| `save_results()` | 検証完了した抽出結果・snapshot・取得日時・環境・各種ハッシュ・SQLをローカル保存 |

`con` は生のDuckDB接続ではなく、この実験の接続と再現情報を保持する小さなセッションです。カテゴリ不一致はmanifestに残し、存在する場合だけ短い警告を表示します。カテゴリ名が辞書に存在しない場合は、0店舗と誤解しないよう停止します。取得したDataFrameを加工してからカテゴリ関数へ渡した場合も、保存結果との食い違いを防ぐため停止します。別のAOIを取り直したらカテゴリ抽出もやり直してください。

実装は [foursquare.py](../src/geoai_open_lab/foursquare.py)、保存処理は [_foursquare_provenance.py](../src/geoai_open_lab/_foursquare_provenance.py) に分けています。各関数のdocstringも参照できます。token・署名付きURLを含み得る例外本文は表示しません。内部モジュールも公開コードであり、「内部」はNotebookから詳細を隠すという意味です。

## 対象範囲と確認すること

[configs/aoi/kichijoji.toml](../configs/aoi/kichijoji.toml) のWGS84矩形を使用します。西139.574、南35.699、東139.586、北35.708、境界を含みます。これは筆者定義の約1 km四方の実験範囲で、正確な駅座標・徒歩圏・行政境界ではありません。AOIを変更すると別の実験になります。

Notebookはテーブル一覧・実スキーマ・snapshotを確認した後、`country = 'JP'` とbboxを同時に適用します。今回の実接続ではテーブル一覧が空でも公式名で直接参照できたため、一覧が空の場合は公式テーブルのDESCRIBEで確認します。日本全体の件数走査は行わず、AOI内にJPのレコードが存在することを確認します。POIはID順で最大500件＋上限判定用1件を読み、保存は最大500件です。これは無作為標本ではありません。`LIMIT` は返却件数の制限であり、通信量や走査量の上限を保証しません。

取得件数とAOI全件数を混同しないよう、上限到達時は `truncated = true` と記録します。閉店フラグで事前除外せず、閉店日あり・なしを別々に数えます。Categoriesは小さな辞書として上限5000件＋1件で取得し、上限超過や重複IDを検出したら停止します。

カフェ抽出は実際のCategoriesの名称が `cafe / café / coffee shop`（大文字小文字を区別しない）に完全一致するカテゴリIDを見つけ、階層の子カテゴリも含めてIDでJOINします。CafeteriaやInternet Cafeは部分一致で含めません。名称の完全一致は候補カテゴリの選定にだけ使い、店名からカフェを推定しません。複数カテゴリによるPOI重複を `EXISTS` で回避します。結果は**取得した最大500件の範囲内**のカテゴリ抽出であり、吉祥寺全域のカフェ総数や網羅性を示しません。

## snapshotと再現記録

初回はPlacesとCategoriesそれぞれのsnapshot一覧から、`timestamp_ms`、`sequence_number`、`snapshot_id` の降順で先頭を選びます。これは「一覧内で最も新しく作成されたsnapshot」であり、ロールバック後のcurrentポインタとの一致を保証するものではありません。選択したIDと日時を必ず明示し、全クエリを `AT (VERSION => ID)` に固定します。

選択結果は `data/cache/foursquare/snapshots.json` に保存し、次回は同じIDを使用します。別の実行を再現する場合は `connect_foursquare(snapshot_ids={"places": "記録されたID", "categories": "記録されたID"})` のように両方を指定します。通常のNotebookでは保存済みIDを自動使用します。IDが失効・削除されている場合はエラーで停止し、latestへの自動フォールバックはしません。更新する場合だけローカルのpinsファイルを退避して新しい実験として実行してください。

`data/raw/foursquare/<UTC時刻とランダムID>/` に以下を保存します。

- `places.json`、`categories.json`、`cafes.json`: ローカルの抽出結果。
- `manifest.json`: Places / Categoriesの個別snapshot ID・時刻、取得開始/終了UTC、AOI、フィルター、件数、上限判定、Python / DuckDB / 拡張の版、ソースコードとlockfileのSHA-256、出力ファイルのSHA-256、公式文書URL。

releaseの月次名称とsnapshot IDの対応が公式metadataから確認できない場合、release labelは未特定のままにします。取得日時をsnapshot日時として代用しません。Icebergの履歴保持と将来の取得可否は提供者次第です。記事に掲載するのは安全性を確認したメタデータと観察結果だけにしてください。

## 検証状況

実際に行った検証と接続上の制約は [検証記録](foursquare-validation.md) に記載します。認証前のテスト結果をFoursquare実データの結果として扱わないでください。
