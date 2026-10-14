# 吉祥寺のPOI地域特徴量

[Notebook](../notebooks/05_region_features.ipynb) / [検証](region-features-validation.md) / [記事引き継ぎ](region-features-article-handoff.md)

保存済みOverture Placesの登録件数・密度・カテゴリ構成を、吉祥寺の実験用矩形の内部で比較する。街同士の比較、普遍的分類、営業中店舗数や人流の推定は行わない。

## 固定入力

[設定](../configs/region_features.toml)が入力と条件の正本。自動的に最新ファイルを選ばない。

- release: `2026-09-23.0`、schema: `v2.0.0`
- 取得実行: `20260925T115558Z-2f21beb2`、完了: `2026-09-25T11:55:58.750623+00:00`
- 入力: `data/raw/overture/20260925T115558Z-2f21beb2/places.parquet`、688,915 bytes、3,666行
- SHA-256: `341993b170f5903c1725551a01850ca14094b9b2e76087b86be8e8aef60b9011`
- 取得manifest SHA-256: `7883ae09a26eb546e52849d7d9dc5107132cd08d22de0b1e1b8eb931a1e1bff5`
- AOI: [kichijoji.toml](../configs/aoi/kichijoji.toml)、西139.574・南35.699・東139.586・北35.708、EPSG:4326、外周を含む
- LIMIT・country・営業状態・confidenceによる除外なし。保存されたAOI取得結果の全件であり、実世界の全店舗という意味ではない。

入力と取得manifestのハッシュ、release、AOI、件数、IDの一意性、座標を確認してから集計する。必要列は `id / geometry / basic_category / taxonomy.primary / taxonomy.hierarchy / taxonomy.alternates / operating_status`。DuckDBによる全列スキーマを生成manifestにも記録する。取得方法は[Overture編](overture.md)を参照。

## 空間集計

- JGD2011 / Japan Plane Rectangular CS IX（EPSG:6677）。pyprojの `always_xy=True` により、コードのxは東、yは北。日本の平面直角座標の通常のX・Y表記と混同しない。
- 投影座標の原点 `(0, 0)` に固定した250m・500m格子。国勢調査の地域メッシュとは別の独自格子。
- 内部境界は `[下限, 上限)` として東側・北側に割り当てる。10nm以下の丸め誤差を補正。AOI外周は包含し、通常の割当先が面積ゼロの場合のみ、外周を覆う区画を行・列順で一意に選ぶ。1μmの投影境界誤差を許容する。
- 緯度経度矩形の各辺を100分割して投影し、格子との交差面積を使用する。投影後の外接矩形で代用しない。1000分割との面積差も監査する。
- 密度は登録件数 / AOI内の実面積(km²)。端の小さい区画も一律62,500m²にはしない。
- 500mは同一原点・入力・採用条件。250mの件数・面積を親格子へまとめた値と照合する。

## カテゴリ・分母・欠損

各POIを単一の `basic_category` で1回だけ数える。taxonomyのprimary・hierarchy・alternatesは保存するが、展開して複数回数えない。元のbasic_category別集計を残す。

図だけの大分類は設定の `display_groups` に固定する。食事=`restaurant, casual_eatery`、カフェ=`cafe, coffee_shop`、バー=`bar`、衣料=`fashion_and_apparel_store`、美容等=`personal_or_beauty_service`、食品小売=`food_and_beverage_store`。これは本実験の表示用であり、全飲食業などを包括する体系や3provider共通カテゴリではない。未掲載の既知分類は `__OTHER__`、null/空文字は `__MISSING__` と分ける。

構成比の分母は各格子の全登録件数（欠損も含む）。カテゴリ0件は比率0、格子全体0件の構成比は未定義。取得不完全なら集計を停止し、未取得を0件扱いしない。営業状態も欠損を別項目で集計し、欠損を営業中や閉店とは判定しない。

## 再現

`projects/poi/` で実行する。入力ファイルと取得manifest、DuckDB spatial拡張の既存キャッシュが必要。公開リポジトリには生データを含めないため、新規cloneだけでは今回の固定入力は揃わない。ファイルがなければ停止し、別releaseに置き換えない。追加取得には別途判断が必要。

```powershell
uv sync --locked --group notebooks --group osm
.venv/Scripts/python.exe -c "from geoai_open_lab.region_features import run_experiment; from geoai_open_lab.region_figures import save_figures; r,m,o=run_experiment(); save_figures(r,o); print(m['summary'])"
.venv/Scripts/python.exe -m jupyter lab notebooks/05_region_features.ipynb
```

既存環境では `uv sync --locked --offline --group notebooks --group osm --no-install-project --inexact --cache-dir data/cache/uv` を確認した。これはインストール済みの本プロジェクトを再構築しないためのコマンドで、新規環境向けではない。既存osmグループが持つpyproj・shapely・pyarrowを再利用しており、OSMデータは使用しない。Matplotlibやフォント・背景地図の追加取得はせず、標準ライブラリでSVGを作る。

`load_inputs()` は固定入力の検査と投影、`run_experiment()` は集計・照合・manifest保存、`save_figures()` は共通色尺度の地図と構成比図を担当する。Notebookはこの3関数を使う。

出力先は `data/cache/region_features/kichijoji-v1/`。再実行で同じ名前を上書きする。`cells_*.csv`、`category_*.csv`、`display_group_*.csv`、`status_*.csv`、`assigned_*.parquet`、`manifest.json`、SVGを保存する。manifestに実行日時UTC、環境、入力・コード・設定・表のハッシュを残す。実行済みNotebookとHTMLも同フォルダに置き、Gitへ追加しない。

## 出典・公開条件（2026-10-14確認）

既存Overtureデータの条件は[利用ガイド](overture.md)を引き継ぐ。[公式Attribution](https://docs.overturemaps.org/attribution/)・[Places](https://docs.overturemaps.org/guides/places/)・[FAQ](https://overturemaps.org/about/faq/)を再確認した。PlacesにはCDLA-Permissive-2.0、Apache-2.0、CC0のソースがあり、コードのApache-2.0で外部データを再ライセンスしない。FAQが示す分析結果とデータ再配布の区別に基づき、今回公開するのは方法・集計値の説明。生データ・POI別表は公開しない。図にはOverture Maps Foundation、release・取得日を表示する。記事にも公式Attributionへのリンクを付ける。レコードを再配布する場合はソースごとのNOTICE等を別途確認する。

座標系の選択根拠：[国土地理院・平面直角座標系](https://www.gsi.go.jp/sokuchikijun/jpc.html)。本実験は位置精度・カテゴリ精度・網羅性を保証せず、重複IDがないことは実店舗の重複がないことを意味しない。
