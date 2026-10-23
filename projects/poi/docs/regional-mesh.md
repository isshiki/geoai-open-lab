# 標準地域メッシュで人口とPOIを結合する

[Notebook 12](../notebooks/12_regional_mesh.ipynb) / [検証](regional-mesh-validation.md) / [記事引き継ぎ](regional-mesh-article-handoff.md)

地域メッシュは、統計を共通の区画とコードで扱うための仕組み。駅を中心とする範囲や、唯一正しい街の境界ではない。POI連載の基礎回として配置し、既存のNotebook 01〜11bと数値は変更しない。

## 公式仕様（2026-10-23確認）

昭和48年行政管理庁告示第143号とJIS X 0410が地域メッシュの区分・コードの基礎。今回は統計局の公式解説・区分図とe-Stat定義書を実装根拠にした。JIS規格本文そのものの全条文適合性検査はしていない。

| 区分 | 親からの分割 | 緯度間隔 | 経度間隔 | 桁数 | およその大きさ |
| --- | --- | --- | --- | --- | --- |
| 第1次 | 緯度40分、経度1度 | 40分 | 1度 | 4 | 80km |
| 第2次 | 第1次を縦横8等分 | 5分 | 7分30秒 | 6 | 10km |
| 第3次（基準地域メッシュ） | 第2次を縦横10等分 | 30秒 | 45秒 | 8 | 1km |
| 2分の1地域メッシュ | 第3次を縦横2等分 | 15秒 | 22.5秒 | 9 | 500m |
| 4分の1地域メッシュ | 500mを縦横2等分 | 7.5秒 | 11.25秒 | 10 | 250m |

e-StatのT001142定義書p.2は「4次（500m）」「5次（250m）」とも表記する。本文では「2分の1地域メッシュ（約500m）」を基本にする。名称の500mは厳密な辺長ではない。今回の各500mメッシュ面積は約0.2614km²であり、0.25km²を代入しない。

先頭2桁は緯度×1.5の整数部、次の2桁は経度の整数部−100。第2次の2桁は南から北・西から東の0〜7、第3次の2桁は同じ順の0〜9。500m・250mの追加桁は1＝南西、2＝南東、3＝北西、4＝北東。コードは文字列。250mコードの最後の1桁を落とすと500mの親コードになる。

## 固定範囲と計算

既存のN02-25吉祥寺代表点と1km四方に、正の面積で交差する500mメッシュを全て選ぶ。境界でメッシュを切らず、区画全体を採用する。これは駅中心1km四方そのものの人口ではなく、9区画・約2.353km²の統計である。面積按分や人口の補間は行わない。

- `encode_mesh(latitude, longitude, digits=8/9/10)`：JGD2011緯度経度からコードへ。南・西端を含み北・東端を含まない。角度の整数格子座標を小数9桁へ丸め、約0.001mm以下の計算誤差を境界へ寄せる。測位精度を保証するものではない。
- `mesh_bounds` / `mesh_polygon`：コードからEPSG:6668の境界を復元。投影時は各辺を8分割してEPSG:6677へ変換する。
- `aggregate_population`：各500mの250m子区画4個の人口総数だけを合計。未掲載・欠損の子区画があれば親の人口は欠損とし、0や部分合計を人口総数として提示しない。
- `run`：ハッシュ・取得範囲・行数・IDを検査し、POIを1つのコードに割り当て、人口と結合。取得済み範囲を確認した後のPOI0件と、未取得を区別する。入力不足なら停止し、自動取得しない。

POIは全営業状態を含む登録数。人口は常住人口で、訪問者・昼間人口・最新人口ではない。重複する実施設が複数IDで登録される可能性は残り、IDの一意性は実店舗数の正確性を保証しない。

## 人口・秘匿の扱い

`tblT001142Q5339.zip`内の`tblT001142Q5339.txt`をCP932、2段ヘッダとして読む。統計表T001142「人口及び世帯」、2020-10-01、JGD2011版250mメッシュ。人口総数の列は定義書p.1の`T001142001`で固定し、列位置に依存しない。

定義書p.2では男女別人口総数等は秘匿しない項目。`HTKSYORI=2`は秘匿元、1は合算先、0は対象外、`HTKSAKI`・`GASSAN`は合算関係を示す。秘匿する年齢内訳等を人口総数へ加えたり、合算先へ人口総数を再加算したりしない。本実験は人口総数のみを利用し、年齢・世帯内訳の集約へそのまま流用しない。元フラグと合算欄は監査CSVへ保存する。対象36区画は全て0。

250m公表値を独自に500mへ合計する実験であり、別配布の公式500m人口表との数値一致は未確認。公式ポリゴンGISも新規取得せず、区分図の既知の境界と、配布コードの復号・再符号化で対応を確認した。幾何の独立した頂点照合ではない。

## 座標参照系

JGD2011は測地系の名称で、人口の調査年ではない。コード計算・境界生成はJGD2011緯度経度のEPSG:6668。面積と地図表示はJGD2011 / 平面直角座標系第IX系（EPSG:6677）。`always_xy=True`で経度・緯度、東・北の順に統一する。緯度経度のdegree²をkm²として扱わない。

OvertureのEPSG:4326から6668へpyprojで変換する。今回選ばれた操作の公称精度は1mで、境界付近の割当には座標精度・時期の不確かさが残る。座標エポックを使った地殻変動補正は行っていない。PROJのネットワークは無効化する。EPSGの詳しい解説は次の記事へ分ける。

## 入力・ライセンス

| 入力 | 固定版・取得日時UTC | SHA-256・保存先 |
| --- | --- | --- |
| 国勢調査 | 2020-10-01、T001142、JGD2011、既存取得2026-10-03T10:57:41.544072+00:00 | `3e29a001e4fc0cfdd840a2885b6ab68cc183c79742e072f33e0ff906250e2d81`、`../../station-territory/data/raw/tblT001142Q5339.zip`（テーマからは`../station-territory/data/raw/`） |
| Overture Places | 2026-09-23.0、schema v2.0.0、2026-10-15T08:01:26.347545+00:00 | `77f385ecf6cfcddf9eb8415ba6db76472cd72f4a7b7a61ec446b90a0a99869e8`、テーマ内`data/raw/similar_regions/20261015T080101Z-tokyo/places.parquet` |
| 駅代表点 | 国土数値情報N02-25を加工、既存設定を再利用 | [駅中心AOI](../configs/aoi/kichijoji_station_1km.toml)、[取得・統合記録](region-feature-sources.md) |

人口ZIPは3,306,040 bytes。元取得記録はstation-territoryの`data/reference/population-manifest.json`。コピー時刻を取得日としない。元POIのsources・license列は元Parquetに保存したまま、今回の割当キャッシュはIDと位置・コードに限定する。manifestは元ファイルとスキーマ・取得日・ハッシュを記録する。

e-Statは出典と加工の明記を条件に利用できる（第三者権利・適用除外は別途）。表記は「総務省統計局『令和2年国勢調査に関する地域メッシュ統計』を加工」。図は公式作成物と誤認させない。Overture Placesはソースごとの条件があり、Foursquare由来はApache-2.0とNOTICE、他のソースにはCDLA-Permissive-2.0等がある。元の利用条件をコードのApache-2.0で上書きしない。[Overture条件](overture.md)と既存取得時のライセンス記録も維持する。

本実験の地図・集計図はこれらの出典・加工表示を付け、ローカルの記事素材として生成する。既存Foursquare NOTICE全文とApacheライセンスのコピー、2026-10-23の加工内容を成果物フォルダへ付ける。記事側は出典URLとNOTICEへの導線を維持する。生データ・機械可読集計表・画像・HTMLをGitへ追加しない。新規の集計データ再配布は今回の公開対象に含めない。

## 再実行

`projects/poi/`で既存uv環境を使用する。新規cloneには入力が含まれないため、既存の[人口出典](../../station-territory/docs/data-sources.md)・[POI取得手順](similar-regions-design.md)で固定入力を準備する。取得不能なら別版に切り替えない。自動ダウンロードはない。

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD 'data/cache/uv'
uv sync --locked --offline --group osm --group notebooks
uv run --no-sync python -m geoai_open_lab.regional_mesh
uv run --no-sync python -m geoai_open_lab.regional_mesh_figures
uv run --no-sync python scripts/execute_regional_mesh_notebook.py
uv run --no-sync python -m unittest discover -s tests -p test_regional_mesh.py
```

PNGは既存のPlaywrightとローカルChromium系ブラウザで`node scripts/render_regional_mesh.cjs`。必要なら`NODE_PATH`で既存モジュール位置、`BROWSER_EXECUTABLE`で実行ファイルを指定する。ネットワーク要求を遮断してSVGを描画する。ブラウザ・依存の自動追加はしない。生成物は`data/cache/regional_mesh/kichijoji-v1/`。

## 公式出典（資料・条件は2026-10-23確認、配布URLは既存記録を継承）

- [統計局：地域メッシュ統計について](https://www.stat.go.jp/data/mesh/m_tuite.html)：制度・区分・角度間隔。
- [統計局：地域メッシュ区分図](https://www.stat.go.jp/data/mesh/pdf/m-kukaku.pdf)：p.1〜5の区分と番号付け。
- [統計局：用語](https://www.stat.go.jp/data/mesh/yougo.html)：JIS X 0410、標準地域メッシュ、測地系。
- [e-Stat：T001142定義書](https://www.e-stat.go.jp/help/data-definition-information/downloaddata/T001142.pdf)：p.1調査日・表・列名、p.2秘匿しない項目とフラグ・桁数。
- [e-Stat：固定人口配布元](https://www.e-stat.go.jp/gis/statmap-search/data?statsId=T001142&code=5339&downloadType=2)：データの再取得は今回未実施。
- [e-Stat利用規約](https://www.e-stat.go.jp/terms-of-use)：出典・加工表示、第三者権利。
- [Overture Attribution and Licensing](https://docs.overturemaps.org/attribution/)：Placesのソース別条件。
- [N02 2025](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N02-2025.html)：駅の既存出典。今回の代表点は出口ではない。
