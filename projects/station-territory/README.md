# 駅の縄張りランキング

東京23区の駅を、歩行道路網による縄張りの面積・推計人口・OSM登録POI数・人口加重平均道のりで集計します。POI記事シリーズとは独立したテーマです。

[Notebook](notebooks/01_rankings.ipynb) / [定義と限界](docs/method.md) / [入力と公開条件](docs/data-sources.md) / [検証](docs/validation.md) / [記事引き継ぎ](docs/article-handoff.md)

## 実行

このディレクトリ `projects/station-territory/` で実行します。依存環境・uv.lockはPOIプロジェクトと独立しています。

```powershell
uv sync --locked --group notebooks
uv run --locked python -m unittest discover -s tests -v
# sourceに、取得済み入力を持つローカルeki-walk cloneを指定します。
uv run --locked python -m station_territory.import_inputs --source <eki-walkのローカルclone>
uv run --locked python -m station_territory.pipeline
uv run --locked --group notebooks jupyter lab notebooks/01_rankings.ipynb
```

インポートは既存入力をコピーし、サイズ・SHA-256を記録します。元プロジェクトを変更せず、旧結果は `data/reference/` へ分離して計算入力にしません。新規取得を自動で行う機能はありません。入力を持たない読者は [出典](docs/data-sources.md) と固定版を確認して準備する必要があります。

DuckDB 1.5.5のローカルspatial拡張が必要です。Windowsでは `data/cache/duckdb/extensions/v1.5.5/windows_amd64/spatial.duckdb_extension` へ置きます。自動INSTALLは行いません。別OSの拡張パス・実行は未検証です。

原PBFから東京の道路格子も作り直す場合：

```powershell
uv run --locked python -m station_territory.replay_grid
```

結果は `data/replay/` へ分離し、インポートした格子を上書きしません。道路読込はDuckDBのメモリ上限4GBを使います。集計・図版は `data/results/` と `data/figures/`、実行済みNotebook・HTMLは `data/cache/`。すべてGit管理外です。実行前に補助ファイルの保存先も設定します。

```powershell
$env:IPYTHONDIR = Join-Path $PWD 'data/cache/ipython'
$env:JUPYTER_RUNTIME_DIR = Join-Path $PWD 'data/cache/jupyter/runtime'
$env:MPLCONFIGDIR = Join-Path $PWD 'data/cache/matplotlib'
```

## 解釈と公開

高齢化率と非人口加重平均距離のランキングは扱いません。人口ありメッシュ面積は住宅用地面積ではなく、POI登録数は実店舗数ではありません。人口は2020年メッシュの面積按分で、実際の通勤距離や利用者数を表しません。

図版署名は [masahiko.info](https://masahiko.info/) をタイトルと同じ高さの右上へ読みやすい大きさで表示します。出典は別に表示します。図表のブログ掲載前にはODbL・N03の利用条件を公開形態に応じて確認してください。

オリジナルコードは [Apache-2.0](LICENSE)。移植コードの由来と変更は [NOTICE](NOTICE.md)。外部データのライセンスは別です。[全体データポリシー](../../docs/data-policy.md) に従い、ダウンロードとpushは都度ユーザー確認後に行います。
