# メッシュ方式比較：方法・公式出典

確認日：2026-10-23。記事1は「地図のメッシュ入門　標準地域メッシュ・H3・S2・独自グリッドをPythonで比較」。[Notebook 13](../notebooks/13_mesh_systems_comparison.ipynb) / [検証](mesh-systems-validation.md) / [記事引き継ぎ](mesh-systems-article-handoff.md)。Notebook 12と既存結果は変更しない。

## 何を比較するか

|方式|分類・主用途|範囲|統計との直接結合|サイズ・原点の自由度|階層・近傍|
|---|---|---|---|---|---|
|標準地域メッシュ|日本の公的統計区画|日本の統計に使用|対応する年・測地系・桁の統計とコード結合|規定。任意変更不可|4/6/8/9/10/11桁。本比較は辺共有4近傍|
|H3|全球階層空間インデックス|全球|元資料がH3 IDを持つ場合のみ直接。それ以外は再集計|resolution選択、原点固定|通常7子、grid_diskで近傍。五角形の例外あり|
|S2|全球階層空間インデックス|全球|元資料がS2 IDを持つ場合のみ|level選択、原点固定|4子、get_edge_neighborsで辺共有4近傍|
|Geohash|緯経度を文字列へ符号化|全球|標準メッシュ統計とは直接不可|文字数選択、原点固定|1文字追加で32子。今回は辺共有4近傍|
|XYZ|Web地図表示・配信用タイル|Web Mercator、極域を除く|統計区画ではない|zoom選択、原点固定|4子。x/yの±1で辺共有近傍|
|Quadkey|同じタイルの階層ID|XYZと同じ|XYZと同じ|XYZと同じ|末尾1桁を戻すと親、4子|
|MGRS|位置参照用グリッド|UTM/UPSで全球。本実装は日本のUTM域のみ検証|標準メッシュ統計とは直接不可|位置精度の桁数選択、ゾーン規定|東西・南北各1桁追加で100子。今回は投影座標で4近傍|
|独自正方形|分析用区画|指定した座標系の有効範囲|独自に座標を割り当てる|自由。本実験は500m、原点(0,0)|幅を倍・半分にして4子、4近傍|
|独自六角形|分析用区画|同上|独自に座標を割り当てる|自由。本実験は外接半径300m|6近傍。階層は設けない|
|OGC DGGS|概念・標準の枠組み|全球格子を扱う枠組み|個別実装・データ次第|個別実装次第|単一ID方式ではない。本実験は適合性検査ではない|

## 計算条件

- 主例：既存N02-25由来の吉祥寺代表点、緯度35.70314448120142・経度139.57980985190306。比較用の札幌付近(43.06,141.35)、那覇付近(26.21,127.68)は任意に固定した座標で、駅の公式座標ではない。
- 各方式のレベルは実測前に固定：標準2分の1、H3 res8、S2 level14、Geohash6文字、XYZ z16、Quadkey16桁、MGRS precision2（投影上1km）。同面積になるように最適化した比較ではない。MGRSには精度桁として500mがない。
- 独自グリッドは東京だけ。EPSG:6677（JGD2011 / 平面直角座標系第IX系）、東西x・南北y、原点(0,0)m。正方形はfloorで南西を含み北東を含まない。六角形はflat-top、軸座標q/r、最近中心へ割当し同距離は(q,r)辞書順。外接半径300m、投影上の面積は約0.233827km²。階層的に六角形を単純4分割できるとは説明しない。
- 標準メッシュは4326→6668を明示してから既存のコード規則を使用。図の位置は6677へ投影。S2・H3のライブラリが返す球面境界頂点も、共通のWGS84楕円体ポリゴン面積へ換算して比較する。これは各ライブラリ固有の球面面積APIの出力そのものではない。
- 緯経度直線境界と投影直線境界は辺を16分割して面積計算。H3/S2頂点間は楕円体測地線として面積評価する近似。全球や日付変更線、極域、MGRSゾーン境界の汎用実装を主張しない。3地点に対する包含・親子・近傍を検証する。
- 投影上の0.25km²と地表面積は厳密には同じでない。標準500mも等面積ではない。H3/S2の面積変動を緯度だけの関数と説明しない。H3の親子IDは厳密な論理階層だが、子の形状が親に完全包含されるとは限らない。

## 依存とライセンス

専用dependency group `mesh-systems`を追加。既存パッケージの版は変更していない。初回の環境構築のみネット接続が必要となる場合がある。以降の計算はネットワーク不要。

|採用|版|公式性・保守確認|ライセンスと採用範囲|
|---|---|---|---|
|h3|4.5.0|Uber H3公式Python binding、4系API|Apache-2.0。点・境界・親子・近傍|
|s2sphere|0.2.5|Sidewalk Labsの非公式Python移植。リポジトリはarchive、保守終了|MIT。軽量な純Python版を隔離して採用。公式S2 C++全機能の代替や本番推奨とはしない|
|mgrs|1.5.4|HobuのGEOTRANS由来binding、NGAの公式Python配布ではない|リポジトリLICENSEはMIT。PyPIのBSD分類と混同しない。日本のUTM域で点・コードを使用|
|future（間接）|1.0.0|s2sphereの依存|MIT|
|pyproj / Shapely / pandas|既存固定版|既存uv環境を継続|既存ライセンスを維持。面積・形状・表を処理|

Geohash、XYZ、Quadkey、独自グリッドは出典の規則から小さな関数を実装（外部コードの転載ではない）。標準メッシュの8〜10桁は既存実装を再利用し、入門用の親子操作と4・6・11桁を別モジュールに追加した。標準の全範囲・全JIS適合性を認証した実装ではない。

## 公式・開発元資料

すべて2026-10-23確認。個別仕様と今回の実測は区別する。

- [統計局：地域メッシュ統計](https://www.stat.go.jp/data/mesh/m_tuite.html)、[区分図 PDF pp.1–6](https://www.stat.go.jp/data/mesh/pdf/m-kukaku.pdf)、[用語](https://www.stat.go.jp/data/mesh/yougo.html)。JIS X 0410と統計区画。125mは区分図の「参考」。JIS本文を複製しない。
- [H3公式](https://h3geo.org/docs/)、[Python API](https://uber.github.io/h3-py/api_quick.html)、[面積と五角形](https://h3geo.org/docs/core-library/restable/)。[h3-py](https://github.com/uber/h3-py)のApache-2.0表示を確認。
- [S2公式階層](https://s2geometry.io/devguide/s2cell_hierarchy.html)、[採用Python実装・MIT](https://github.com/sidewalklabs/s2sphere)。公式S2のライセンスと採用bindingのライセンスを区別する。
- [Geohash実装著者の説明](https://www.movable-type.co.uk/scripts/geohash.html)、[OpenSearchのGeohash仕様説明](https://docs.opensearch.org/latest/aggregations/bucket/geohash-grid/)。単一の世界標準認証規格とは扱わない。
- [Microsoft：Bing Maps Tile System](https://learn.microsoft.com/en-us/bingmaps/articles/bing-maps-tile-system)。タイルAPIや画像は取得せず、座標計算規則だけ参照する。
- [NGA：Coordinate Systems](https://earth-info.nga.mil/?action=coordsys&dir=coordsys)、[mgrs LICENSE](https://github.com/hobuinc/mgrs/blob/main/LICENSE)、[PyPI mgrs](https://pypi.org/project/mgrs/)。GEOTRANS由来処理を含むが、NGAによる今回の結果保証ではない。
- [OGC DGGS](https://www.ogc.org/standards/dggs/)。方式一覧のどれも無条件にOGC適合と書かない。

本比較はアルゴリズムで区画を生成し、外部の図・背景地図・データセットを再配布しない。コード・自作説明はApache-2.0、外部ライブラリは各ライセンス。人口・POIの既存応用は[既存データ条件](regional-mesh.md)とNOTICEを維持する。新しい生データの取得はない。

## 再実行

`projects/poi/`を作業ディレクトリとする。

```powershell
uv sync --locked --all-groups
uv run --no-sync python -m geoai_open_lab.mesh_systems
uv run --no-sync python -m geoai_open_lab.mesh_guide_figures
uv run --no-sync python scripts/execute_mesh_systems_notebook.py
uv run --no-sync python -m unittest discover -s tests -p test_mesh_systems.py -v
```

SVGからPNGへの変換は既存Node/PlaywrightとローカルChromium系ブラウザで`node scripts/render_mesh_guides.cjs`を実行する。`BROWSER_EXECUTABLE`で既存ブラウザを指定可能。ブラウザ自動ダウンロードや地図タイル通信は行わない。

出力は`data/cache/mesh_systems/comparison-v1/`と`data/cache/regional_mesh/guide-v1/`。前者にcomparison.csv・cells.json（境界、全子ID、近傍ID）・manifest.json・実行Notebook/HTMLを保存。公開対象はコード、出力なしNotebook、文書、テストのみ。既存`kichijoji-v1/`は読み取りも書き換えもしない（保全照合を除く）。
