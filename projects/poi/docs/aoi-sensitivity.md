# 正方形AOIの感度検証

[Notebook 09](../notebooks/09_aoi_sensitivity.ipynb) / [固定仕様](aoi-sensitivity-design.md) / [検証](aoi-sensitivity-validation.md) / [記事資料](aoi-sensitivity-article-handoff.md)。既存Embedding成果を上書きしない。

## 実行

`projects/poi/`で既存uv環境を使用する。依存追加・OS標準Pythonへのインストールは不要。

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD 'data/cache/uv'
$env:PYTHONUTF8 = '1'
uv sync --locked --offline --group clustering --group osm --group notebooks
uv run --no-sync python -m geoai_open_lab.aoi_sensitivity
uv run --no-sync python -m geoai_open_lab.aoi_sensitivity_figures
uv run --no-sync python scripts/execute_aoi_sensitivity_notebook.py
```

PNGは既存Playwright/Edge環境から `node scripts/render_aoi_sensitivity.cjs` で生成。これらの分析・描画コマンドはネットワーク取得をしない。新規cloneは生データを含まず、そのまま実行はできない。

入力は`configs/similar_regions.toml`の取得run、既存Embedding manifestと語彙、`data/raw/aoi_sensitivity/supplement-v1/`の追加入力。追加取得コード`acquire_aoi_supplement.py`は、報告・承認された不足領域を取得するための別コマンドであり、分析中に自動取得しない。取得済みディレクトリの上書きを拒否する。固定releaseを取得できなければ停止し、別releaseへ切り替えない。

## 計算

EPSG:6677で中心から東西南北500/600/700/800m。一辺1.0/1.2/1.4/1.6km、面積1.00/1.44/1.96/2.56km²。点は外周を含めAOIに属する。駅間のAOI重複では同一POIを複数駅へ割当可能。

Aの6群カテゴリ定義は`configs/region_features.toml`をそのまま使用。密度は登録数÷対象面積。250m格子の位置は駅を原点とする格子線で固定（既存の駅から西南500m原点と同じ格子）。内部境界は東・北側へ、外周は内側へ一意割当。部分格子は実面積で密度を計算する。全体平均密度は面積加重であり、格子密度の単純平均ではない。

Bは固定961語彙のprimary件数、smooth IDF・件数TF・L2。CはBへTruncatedSVD64（seed42、n_iter10）、L2。Aの中央値/IQR、BのIDF、CのSVDはAOIごと再学習。新しい細分類が現れても語彙へ追加せず、欠損と語彙外を監査する。Cの軸同士は直接比較しない。

全駅共通の候補規則は、最大800m AOI同士が正面積で重なる候補と自駅を除外。境界の接触だけは除外しない。全656駅の各照会について同じ候補集合で上位10共通数と全順位のSpearmanを計算する。同距離の表示順はregion_id、Spearmanでは同距離に平均順位を使う。

K-meansは各方式の空間でk=3、seed42、n_init30、max_iter500、tol1e-4、lloyd。Bのk=3は今回追加した参考値で、前回記事にBクラスタ結果があったという意味ではない。500mとの最大一致対応とARIを計算。代表駅は各群の中心に近い3駅。群ごとの数値特徴の中央値と主なカテゴリを保存。

## 保存と注意

テーマ内`data/cache/aoi_sensitivity/tokyo-v1/`にCSV、行列、manifest、SVG/PNG、実行済みNotebook/HTMLを保存する。出力は全てGit管理外。sources/licenseは元と追加のParquetに保持。Foursquare NOTICEとApache LICENSEを成果物へ同梱する。[出典条件](region-feature-sources.md)を継承する。

部分格子・再学習を含むパイプライン感度であり、単なる距離パラメータだけの因果効果ではない。円形・徒歩圏・最適商圏は検証していない。

## Aの格子端に関する追加品質確認

記事の順位比較は[追加検証](aoi-sensitivity-validation.md)の完全250m区画版Aを使用する。旧実装と旧成果物は監査用に残す。
保存済みfeatures.csvとaudit.csvのfull_cell_peakをSHA確認して使用し、変更するのは最大密度・集中度だけ。B/Cの学習やクラスタ再計算は行わない。

```powershell
uv run --no-sync python -m geoai_open_lab.aoi_full_cells
uv run --no-sync python scripts/execute_aoi_sensitivity_notebook.py
node scripts/render_aoi_sensitivity.cjs
```

Notebook 09は保存済みの全方式結果を前提にこの追加確認だけを実行する。元分析が無い場合は上記の初回実行手順が必要。
追加成果物は`data/cache/aoi_sensitivity/a-full-cells-v1/`。旧`tokyo-v1/`は上書きしない。
修正版のcluster_metrics.csvとassignments.csvは元分析の複製で、Aのクラスタは旧方式の監査値。図はCの分類だけを使う。
完全区画数は16/16/16/36。探索対象の面積は1/1/1/2.25km²、集中度の分母はAOI全域の平均密度。
