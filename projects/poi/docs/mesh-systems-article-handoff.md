# 記事1：メッシュ方式比較の引き継ぎ

タイトル：**地図のメッシュ入門　標準地域メッシュ・H3・S2・独自グリッドをPythonで比較**。未執筆・未公開。

## 読者へ伝えることと構成

「メッシュ」は万能な一つの規格ではなく、目的が違う区画や位置索引の総称として使われる。公的統計を結合する、全球を検索する、Web地図を配信する、分析区画を設計する、を分けて説明する。

1. メッシュの全体像。9方式とDGGSという枠組みを区別する。
2. 共通の吉祥寺代表点を各方式のIDへ変換する。
3. 区画の形と面積を見る。レベル番号は方式間で同じ意味ではない。
4. 親子と近傍を見る。H3の論理階層と幾何包含の違い、Geohashの32子、XYZ/Quadkeyの同一性。
5. 札幌・東京・那覇の同レベル面積。位置により変わることを示す。
6. 目的別に選ぶ。次の記事で日本の標準地域メッシュを深掘りする。

## 掲載コード

初回は`projects/poi/`で`uv sync --locked --all-groups`。以降はネット不要。

```python
from geoai_open_lab.mesh_systems import run
comparison = run()
comparison.query("city == '東京・吉祥寺'")[["scheme", "level", "cell_id", "area_km2"]]
```

ライブラリの短い例も掲載可能：

```python
import h3
import s2sphere as s2
lat, lon = 35.70314448120142, 139.57980985190306
h3_id = h3.latlng_to_cell(lat, lon, 8)
h3_boundary = h3.cell_to_boundary(h3_id)  # 緯度・経度の順
s2_id = s2.CellId.from_lat_lng(s2.LatLng.from_degrees(lat, lon)).parent(14)
print(h3_id, s2_id.to_token())
```

s2sphereは保守終了済みの非公式部分移植。この記事の検証環境で使用し、本番導入推奨としない。緯度経度順とGeoJSONの経度緯度順を混同しない。

## 掲載値・表

[検証記録](mesh-systems-validation.md)の実測表、[方法](mesh-systems.md)の用途・範囲・自由度表を正本とする。東京の楕円体面積は標準0.261497、H3 0.675644、S2 0.234448、Geohash 0.605994、XYZ/Quadkey 0.246042、MGRS 1.000393、独自正方形0.250047、独自六角形0.233871 km²。

これは「全部が500mの比較」ではない。今回選んだレベルと実面積の比較である。独自正方形の投影上の面積0.25km²と、楕円体上の値は分ける。標準メッシュの0.261497は代表点の単独セルであり、既存9区画の平均ではない。

## 図とキャプション

基底パス：`C:/Projects-GitHub/geoai-open-lab/projects/poi/data/cache/mesh_systems/comparison-v1/`。全てSVGと同名PNG。生成物はGit管理外。

|ファイル|キャプション案|
|---|---|
|overview.svg / .png|統計区画・位置索引・地図タイル・分析区画では目的が異なる。DGGSは枠組み。|
|boundaries.svg / .png|同じ吉祥寺の地点が入る9方式の区画。同縮尺・北向き。選択レベルは互いに同面積ではない。|
|comparison.svg / .png|各方式の実測面積、直接の子数、今回採用した辺共有近傍と用途。IDと形は前図を参照。|
|choice.svg / .png|作業目的から選択肢を絞り、レベル・原点・測地系を確認する。|
|cover_1600x900.svg / .png|同じ地点でも形と面積は異なる。区画は用途で選ぶ。|

実行画面は`13_mesh_systems_comparison.html`、表は`comparison.csv`、境界・親子・近傍は`cells.json`、環境とハッシュは`manifest.json`。図版は自作で背景地図を使用していない。

## 言えること・言えないこと

各方式の目的・今回の3地点の面積差・IDの構造を説明できる。全球の統計や性能ベンチマーク、どの方式が最も正確かの判定はしていない。OGC適合を独自に宣言しない。標準メッシュ以外でも統計を再集計できるが、日本の公表メッシュ表へそのままID結合できるわけではない。

[公式出典・ライセンス・再現手順](mesh-systems.md)を参照。記事2は[標準地域メッシュ入門](regional-mesh-article-handoff.md)。Notebook番号は実装順であり、記事公開順とは一致しない。

公開コード：[Notebook 13](https://github.com/isshiki/geoai-open-lab/blob/main/projects/poi/notebooks/13_mesh_systems_comparison.ipynb) / [実装](https://github.com/isshiki/geoai-open-lab/blob/main/projects/poi/src/geoai_open_lab/mesh_systems.py)。
