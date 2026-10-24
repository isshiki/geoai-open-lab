# 座標系入門：Notebook 14の方法

記事案：**地図の座標系入門　緯度経度・投影法・EPSGをPythonで理解する**。
確認日2026-10-24。[Notebook 14](../notebooks/14_crs.ipynb) / [検証](crs-validation.md) / [記事引き継ぎ](crs-article-handoff.md) / [追加データ条件](crs-data-sources.md)。
既存Notebook 01〜13、地域特徴量・Embedding・人口28,487人／POI4,057件の既存結果を変更しない。

## 固定入力と実行

- 駅：[既存設定](../configs/aoi/kichijoji_station_1km.toml)。N02-25、group003584。経度139.57980985190306、緯度35.70314448120142。N02のJGD2011駅線から6677で決めた既存代表点。実際の出入口ではない。
- POI：Overture 2026-09-23.0、schema v2.0.0。`data/raw/similar_regions/20261015T080101Z-tokyo/places.parquet`、全531,156行、取得2026-10-15T08:01:01.664485〜08:01:26.347545Z。LIMIT・国・営業状態・信頼度フィルターなし。既存manifestの全ハッシュを検査する。
- 列はid、geometry由来lon/lat、basic_category、operating_status。元geometryはOGC:CRS84（WGS84、経度・緯度）。EPSG:4326と軸順が異なることを認識してalways_xyを指定する。
- 固定取得範囲が駅中心±1,000mを覆うことをチェックし、この2km四方内の全POIから比較する。3つの500m範囲はいずれもこの中に収まる。駅中心1km四方の既存3,591件だけでは円の境界精度検証には不適切なので、より広い既存キャッシュを再利用する。
- 世界境界：Natural Earth Admin 0 Countries 1:110m、5.1.1、214,976 bytes。2026-10-24T08:43:35.473574Z取得。SHA-256 `0f243aeac8ac6cf26f0417285b0bd33ac47f1b5bdb719fd3e0df37d03ea37110`。Public domain。公式配布URLが更新された場合もhash不一致で止める。

POIテーマを作業ディレクトリにする。OS標準Pythonは変更しない。既存のuv.lockを維持し、追加依存なし。

```powershell
uv sync --locked --all-groups
# Natural Earthがない初回だけ。保存済みなら実行しない。
uv run --no-sync python scripts/acquire_crs_world.py
uv run --no-sync python -m geoai_open_lab.crs_experiment
uv run --no-sync python -m geoai_open_lab.crs_figures
uv run --no-sync python scripts/execute_crs_notebook.py
uv run --no-sync python scripts/run_crs_tests.py
```

SVG→PNGは既存のNode/Playwrightとローカルブラウザを使用する。再取得・自動インストールしない。`NODE_PATH`と`BROWSER_EXECUTABLE`で既存環境を指定して `node scripts/render_crs.cjs`。HTTP(S)通信を遮断して描画する。図のPNG生成後に `uv run --no-sync python scripts/verify_crs_results.py` でCSV完全一致・図の存在・出力なしNotebookを検査する。

`run_crs_tests.py`は既存の全テストを発見して実行する。既存MAUPテストが保存結果を書き直すため、その出力先だけをコピーした一時フォルダへ差し替える。テスト自体を省略しない。Notebook 14の出力には既存Foursquare NOTICE全文とApache LICENSEを同梱し、今回の変更日を追記する。

出力はすべて `data/cache/crs/kichijoji-v1/`。数値CSV、POI判定詳細、manifest、SVG/PNG、実行済みNotebook、HTMLをGitへ入れない。`scripts/check_crs_preservation.py snapshot` と同スクリプトの引数なし実行で旧成果物のハッシュを前後比較する。既存結果を再生成するコマンドは呼ばない。

## 計算の定義

1. PROJネットワーク取得を無効にする。`Transformer.from_crs(..., always_xy=True)`で軸順を経度・緯度／東・北へ正規化。PROJ/EPSG DB版、変換の名称と公称精度をmanifestへ残す。
2. 距離例は、既存代表点からWGS84楕円体の測地線で北100m、東500m、北東500m、南1,000mの説明用地点を作る。同じ端点の測地線距離と平面距離を比較。標高・道路・坂・徒歩時間ではない。
3. 緯度経度のユークリッド距離は単位が度で、メートル距離として無効。CSVの`invalid_degrees_as_m_*`は「度をそのままmと誤読した場合」だけの反例であり、妥当な単位変換ではない。
4. POI採用条件は測地線距離≤500m、および各投影座標系の500mバッファーによる`covers`（境界を含む）。四分円512分割、最大半径不足0.000589m。ポリゴン判定と正確な平面距離≤500mの全POI一致も実行時検査する。方式間の共通数・和集合・Jaccard・片側のみ・対称差・測地線500m境界±1m内の対称差を記録。
5. 世界の面積基準は同じ粗い境界のWGS84楕円体上の測地面積。Polygonごとに外周・穴の向きを整え、島の符号相殺を防ぐ。投影前に辺を10km以下の測地線へ細分化し、投影後直線近似との違いを抑える。細分化前後の測地面積も一致検査。アフリカはCONTINENT=Africaの国ポリゴンをunionし、Greenland・JapanはADMIN属性で選択。国土面積の公式値ではない。
6. 世界表示は177国のうち南極を除く同一データを3方式で描く。南極の極と日付変更線を一続きに投影しない。残りは元データの分割済み日付変更線を維持し、180度超の辺がないことを検査。範囲は3857の利用域内。無効geometryは0件、修復・推測境界なし。緯度経度パネルは横軸経度・縦軸緯度を同じ縮尺で単純表示する。
7. 密度例は実データではない。赤道・北緯35.7度・65度に測地面積100km²の720辺の測地円を二分法で作り、各1,000件の仮想POIを置く。測地面積・3857面積・8857面積の密度を比較。同じ地点の測地線100mの北／東方向を投影し、長さと挟角も測定。等積は距離・形・角度の保存を意味しない。

## EPSGと軸の確認

EPSG RegistryのWebページはアクセス制約があったため、実定義はPROJ同梱EPSG database **v12.029**を`pyproj.CRS`で照合した。正確な名称・軸・単位・適用範囲bbox・datum・ellipsoid・methodをmanifestに保存。公称適用範囲bboxだけで適地を完全判定するものではなく、地域の説明と国土地理院の第IX系対象も照合した。

| EPSG | 正式名称 | 公式軸順／単位 | 適用範囲・方法 |
|---|---|---|---|
| 4326 | WGS 84 | 緯度、経度／degree | 世界。地理座標系、投影法なし、WGS84 ensemble |
| 6668 | JGD2011 | 緯度、経度／degree | 日本陸海域。地理座標系、GRS80楕円体 |
| 3857 | WGS 84 / Pseudo-Mercator | 東、北／metre | 南北約85.06度以内。Popular Visualisation Pseudo Mercator |
| 6677 | JGD2011 / Japan Plane Rectangular CS IX | 北(X)、東(Y)／metre | EPSGの記載は東京都本州陸域（島嶼の別系を除く）。Transverse Mercator |
| 8857 | WGS 84 / Equal Earth Greenwich | 東、北／metre | 世界。Equal Earth、中央経線0度 |

EPSGコードは投影法だけの番号ではない。4326/6668もEPSGコードを持つ。日本の公式X=北、Y=東と、このPythonコードのx=東、y=北は`always_xy=True`による違い。GeoPandasはgeometryをx/yで保持する。`set_crs`は既知の元座標のラベル指定、`to_crs`はそのラベルを用いた座標変換。間違ったラベルを付けると変換後も間違う。

JGD2011を「日本の最新測地系」とは記載しない。今回の固定入力の測地系である。4326↔6677はPROJが選ぶJGD2011 to WGS84 (1)の逆操作を含み、公称精度1m。往復0mは絶対位置精度0mを保証しない。POIの元位置誤差も別に存在する。

## 既存GeoAIコードへの監査

| 段階 | 確認した実装 | 座標系・影響 |
|---|---|---|
| 駅代表点 | [station_square.py](../src/geoai_open_lab/station_square.py) | N02の6668→6677で代表点、保存用に4326へ逆変換 |
| POI→分析 | [region_features.py](../src/geoai_open_lab/region_features.py)、[walking_range.py](../src/geoai_open_lab/walking_range.py)の読み込み | 元CRS84のlon/lat→6677。AOIへの採否に影響 |
| 特徴量 | [region_features.py](../src/geoai_open_lab/region_features.py) | 6677で1km四方・格子・実面積。密度、集中度に影響 |
| 類似検索・分類 | [similar_regions.py](../src/geoai_open_lab/similar_regions.py)、[region_clustering.py](../src/geoai_open_lab/region_clustering.py) | 数値表を距離・K-meansへ入力。座標系を直接入力しない |
| Embedding | [region_embedding.py](../src/geoai_open_lab/region_embedding.py) | カテゴリ件数→TF-IDF→SVD。与えられたPOI集合が同じなら再投影だけでは数値は変わらない |
| 記事図／Web | 今回のSVGは各指定CRS、POI図は6677 | すべての表示が3857とは限らない。一般のWebタイルは3857、APIに渡すlon/latとの区別が必要 |

656駅の固定入力を読み、代表点の適用域とPROJ局所縮尺を検査した。今回の小範囲のPOI分析では距離誤差0.1%以内を目安にすれば十分小さく、6677を維持する。これは測量の精度保証でも、全POIの測位品質確認でもない。世界版「にぎわいの地形図」は別リポジトリを参照・変更しておらず、[記事資料の監査チェックリスト](crs-article-handoff.md)を残す。

## 一次資料（2026-10-24確認）

- [EPSG Registry](https://epsg.org/)、[6677](https://epsg.org/crs_6677/JGD2011-Japan-Plane-Rectangular-CS-IX.html)、[8857](https://epsg.org/crs_8857/WGS-84-Equal-Earth-Greenwich.html)（Webアクセス制約、定義はPROJ同梱DBで照合）
- [PROJ Web Mercator](https://proj.org/en/stable/operations/projections/webmerc.html)、[Equal Earth](https://proj.org/en/stable/operations/projections/eqearth.html)
- [国土地理院・平面直角座標系](https://www.gsi.go.jp/LAW/heimencho.html)、[わかりやすい平面直角座標系](https://www.gsi.go.jp/sokuchikijun/jpc.html)
- [pyproj Transformer](https://pyproj4.github.io/pyproj/stable/api/transformer.html)、[GeoPandas Projections](https://geopandas.org/en/stable/docs/user_guide/projections.html)
- [Natural Earth配布・利用条件](crs-data-sources.md)
- [国連A/RES/80/307原文PDF](https://documents.un.org/api/symbol/access?l=en&s=A%2FRES%2F80%2F307&t=pdf)、[国連Mandate Registryの条文](https://mandates.un.org/mandate/A/RES/80/307?subject=Maps)。第3・5・10・11項および前文を参照。詳しい位置付けは記事資料へ記載。
