# 吉祥寺駅周辺1km四方の地域特徴量

[Notebook](../notebooks/05_region_features.ipynb) / [列定義](region-feature-columns.md) / [検証](region-features-validation.md) / [記事引き継ぎ](region-features-article-handoff.md)

主成果は **1地域＝1行、固定15列** の数値プロフィール。今回は吉祥寺駅周辺1km四方の1行を作る。格子図は算出根拠であり、記事の主役は地域の密度・カテゴリ構成比・集中度である。街同士の比較や類似度は未実施。

[記事『POIデータから作る「地域特徴量」　Pythonで吉祥寺駅周辺を数値化してみた』](https://blog.masahiko.info/entry/2026/10/15/140624)を2026年10月15日に公開した。吉祥寺自体の紹介ではなく、街を比較可能な数値プロフィールへ変換する基礎回。「『吉祥寺』みたいな街を探す」ための土台を作るが、今回だけで吉祥寺らしさや他地域との比較を結論づけない。

## 入力と範囲

[設定](../configs/region_features.toml)と[駅中心AOI](../configs/aoi/kichijoji_station_1km.toml)が正本。

- release `2026-09-23.0` / schema `v2.0.0`。自動でlatestへ切り替えない。
- 取得実行 `20261014T141719Z-station-square`、取得完了UTC `2026-10-14T14:17:39.291936+00:00`。
- 入力 `data/raw/region_features/20261014T141719Z-station-square/places.parquet`、3,591行、362,178 bytes。
- SHA-256 `6a4fc19b49cb5e0c73e61f838baf30e15f86bfd38f71a41919154af7f6034ea2`。
- 取得manifest SHA-256 `dd0f487a3f18582e928189d810ccd1979c432cdcbc9cf0952594e17332c66a01`。
- 国土数値情報N02-25の公式グループ003584の代表駅線中点：経度139.579809851903、緯度35.703144481201。EPSG:6677の東座標-22941.702420628m・北座標-32905.061209669m。
- 中心から東西南北各500mの正方形、1,000,000m²。旧取得矩形は約40,201.594m²を覆わなかったため、必要範囲を同releaseから取得し直した。

EPSG:6677は、JGD2011 / 平面直角座標系第IX系を表す識別番号。東京都周辺の位置をメートル単位で扱い、1km四方や250m格子を計算するために使用する。

駅の出典・取得日・統合規則・CC BY 4.0は[入力と公開条件](region-feature-sources.md)に記録。駅の入口ではない。旧 `configs/aoi/kichijoji.toml` は実験01〜04の再現性のため変更しない。地域特徴量実験は新しい専用AOIを使用する。

## 取得と計算

取得コードは `python -m geoai_open_lab.acquire_station_square`。これは承認された取得作業の明示的実行用で、Notebookから呼ばない。固定N02 ZIPを `data/raw/region_features/station/N02-25_GML.zip` に置き、既存拡張httpfs/spatialをLOADする。対象releaseが取得不能なら停止する。駅代表点は `station_square.station_center()` で公式ZIPから再現できる。

取得は正方形の逆投影境界を1000点で密に計算し、約1cmの余裕を持たせたbboxで候補を読み、EPSG:6677上の正方形で厳密に絞る。LIMIT・country・営業状態・confidenceによる除外なし。必要列 `id, geometry, bbox, basic_category, taxonomy, operating_status, sources` のみ保存。sources内licenseを保持し、全列スキーマ・取得範囲・件数・SHA-256をmanifestに記録する。

投影はalways_xy=True（xは東、yは北）。南西角を格子原点に固定するため、250mは4×4、500mは2×2、部分区画なし。内部境界は東・北側の区画へ一意割当、最外周は包含。許容誤差は既存実装と同じ（格子境界10nm、幾何境界1μm）。全件数・面積・親格子合計を照合する。

平均密度は全件数÷1km²、構成比は各群合計÷全件数。格子の比率を単純平均しない。最大密度は250m区画の最大値、集中度は最大密度÷地域平均。登録数と密度は同じ数値となるが単位・役割が異なるため、類似度へ重複投入しない。

## カテゴリと監査

設定のdisplay_groupsが正本。食事=restaurant/casual_eatery、カフェ=cafe/coffee_shop、バー=bar、衣料=fashion_and_apparel_store、美容等=personal_or_beauty_service、食品小売=food_and_beverage_store。他の既知分類はその他、null/空文字は欠損。単一basic_categoryで数え、taxonomyの階層やalternatesを重複計上しない。

構成比の分母は欠損も含む全件数。0件地域の構成比・集中度は未定義。未取得は0件とせず停止。営業状態欠損は営業中と見なさない。面積・登録数・欠損率・release・取得日・AOI・格子条件は監査情報。密度・構成比・集中度は比較候補であり、採用列・正規化・距離関数は[次段階](tokyo-station-features-plan.md)で決める。

## 再実行

`projects/poi/` で実行する。初回環境は `uv sync --locked --group notebooks --group osm`。今回の既存環境・拡張を再利用し、パッケージ追加なし。固定入力のParquetと取得manifestが必要で、新規cloneには含まれない。取得済み入力がない場合は停止する。

```powershell
.venv/Scripts/python.exe -c "from geoai_open_lab.region_features import run_experiment; from geoai_open_lab.region_figures import save_figures; r,m,o=run_experiment(); save_figures(r,o); print(m['region_profile'])"
.venv/Scripts/python.exe -m jupyter lab notebooks/05_region_features.ipynb
```

出力先 `data/cache/region_features/kichijoji-1km-v2/`（同名出力は再実行で上書き）。主成果 `region_features.csv`・`region_profile.svg`、根拠の格子CSV・密度SVG、manifest、実行済みNotebook・HTMLはGit管理外。NOTICEとApacheライセンスも同フォルダに保存した。公開用Notebookは出力なし。公開物の条件は[出典とライセンス](region-feature-sources.md)を参照。
