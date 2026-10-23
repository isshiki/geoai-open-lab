# 記事2：日本の標準地域メッシュ入門

タイトル：**日本の標準地域メッシュ入門　1km・500m・250mメッシュをPythonで扱う**。未執筆・未公開。記事1の[方式比較](mesh-systems-article-handoff.md)から続く。Notebook番号は実装順であり記事順ではない。

Notebook 12・commit eeeb173の実装と検証は維持する。人口28,487人、POI登録4,057件の結果は失敗例ではなく、この記事の最後の応用を支える。[既存方法・データ条件](regional-mesh.md)と[既存検証記録](regional-mesh-validation.md)は正本のまま残す。

## 初心者へ一言

標準地域メッシュは、日本の公的統計を「同じ場所のコード」で結び付けるための共通の区画です。駅や生活圏に合わせた区画ではありません。

## 記事構成と説明の要点

1. **標準地域メッシュとは**：緯度・経度に基づく共通区画。JIS X 0410と公的統計での位置付けを紹介する。規格本文を転載せず統計局の解説を参照。
2. **階層**：第1次→第2次は8×8、第2次→第3次は10×10。その後は2×2。第1次約80km/4桁、第2次約10km/6桁、第3次約1km/8桁、2分の1約500m/9桁、4分の1約250m/10桁、8分の1約125m/11桁。統計局の区分図は125mを「参考」として掲載。「4次メッシュ」という通称を使う場合も本文では2分の1地域メッシュを基本名にする。
3. **コードの構造**：吉祥寺代表点は`53|39|4|4|4|6|1|4`。53と39で第1次、続く2桁ずつで第2次・第3次。分割の番号1=南西、2=南東、3=北西、4=北東を繰り返す。行・列は南・西を0として数える。
4. **約500mの意味**：緯度・経度の角度幅による区画。500mメッシュの緯度幅15秒・経度幅22.5秒。東西距離は緯度で変わり、メートル単位の正方形ではない。吉祥寺代表点のセルは楕円体面積約0.261497km²（方式比較の新計測）。既存9区画の平均値とは区別する。
5. **座標からコード**：緯度・経度と測地系を確認する。コード自体には調査年・測地系を埋め込んでいない。
6. **コードから境界**：西・南・東・北を復元しポリゴンを作る。境界では南西を含み北東を含まない規則で一意に割り当てる。
7. **親子変換**：250m→500mは末尾1桁を落とす。第3次→第2次は2桁。子へは規則に従う番号を追加。補助実装は125mまで扱うが既存Notebook 12の実装は変更しない。
8. **公的統計との結合**：コードを文字列として保ち、桁・測地系・表定義・年をそろえる。区画が同じでも統計定義が変われば比較条件は変わる。
9. **人口とPOIの応用**：最後にNotebook 12の固定結果を紹介。以下の方法と注意を使う。
10. **最低限の注意**：秘匿・合算・欠損・境界・概数のサイズ・時点を確認。商圏・生活圏の正解ではない。MAUPの検証は再演しない。EPSGの詳細は別記事へ。

## 本文の最小コード

`projects/poi/`のuv環境で実行。既存実装の説明を主にする。

```python
from geoai_open_lab.regional_mesh import encode_mesh, mesh_bounds, mesh_polygon
from pyproj import Transformer

lon, lat = Transformer.from_crs(4326, 6668, always_xy=True).transform(
    139.57980985190306, 35.70314448120142
)
code_500 = encode_mesh(lat, lon, digits=9)   # 533944461
code_250 = encode_mesh(lat, lon, digits=10)  # 5339444614
print(mesh_bounds(code_500))                # 西・南・東・北
polygon = mesh_polygon(code_500)
assert code_250[:-1] == code_500
```

一般の階層を操作する追加補助関数：

```python
from geoai_open_lab.standard_mesh_guide import encode, parent, children, bounds
code_125 = encode(lat, lon, digits=11)
assert parent(code_125) == code_250
print(children(code_500))  # 500mの中の250mコード4個
```

この例は既存の駅代表点の緯度経度を明示的にJGD2011へ変換してから用いる。外部POIも必要な変換をしてから渡す。EPSG:6668はJGD2011の緯度経度、6677は第IX系の平面直角座標。面積を度数のまま計算しない。コードは座標の基準を自動判別しない。

## 最後の応用：人口とPOI

一般的には、POI座標に同じメッシュコードを付け、メッシュ別の登録数・カテゴリ構成を集計し、人口表とコードで結合する。人口当たりPOI数を計算するなら、人口0・欠損の除算結果は未定義として扱う。

```python
# meshesはNotebook 12で検証した結合結果。新規取得はしない。
pop = meshes["population_2020"].where(meshes["population_2020"] > 0)
poi_per_1000 = meshes["poi_count"].div(pop).mul(1000)
```

この人口当たり指標は方法紹介であり、今回の新しい検証結果や需要指標ではない。カテゴリ構成も一般的な拡張例で、Notebook 12に存在しない集計を実測済みと書かない。

既存の応用結果：250m人口36区画→500mの9区画、2020年常住人口28,487人、Overture登録4,057件。対象は駅中心1km四方と交差する**完全な500mメッシュ9区画（約2.353km²）**であり、1km四方そのものではない。旧1km四方3,591件を差し替えない。

人口は2020-10-01の国勢調査T001142・JGD2011版、POIはOverture 2026-09-23.0、取得2026-10-15。対象の人口列は揃い、秘匿フラグ0。常住人口・昼間人口・POI登録数は異なる概念。人口は最新値でも昼間人口でもなく、POIは実店舗数・営業中店舗数ではない。売上・需要・商圏の強さ・出店可否は判断しない。

秘匿・合算の扱いは統計表ごとの定義を確認する。公式500m表との直接照合はしておらず、250m公表値の集約である。測地系の変換精度と元座標の誤差も残る。[既存検証](regional-mesh-validation.md)を参照。

## 新しい入門図版

基底：`C:/Projects-GitHub/geoai-open-lab/projects/poi/data/cache/regional_mesh/guide-v1/`。SVGと同名PNG。

|ファイル|キャプション|
|---|---|
|hierarchy.svg / .png|約80kmから約125mまでの階層。サイズは目安、模様は模式図。|
|code.svg / .png|場所のコードを段階ごとに読む。四分割番号は1〜4。|
|conversion.svg / .png|緯度経度→コード→境界。親子も規則で行き来できる。|
|join.svg / .png|人口とPOIに共通コードを持たせて結合する。時点と意味は異なる。|
|cover_1600x900.svg / .png|1km・500m・250mの区画をPythonで扱う。|

再生成：`uv run --no-sync python -m geoai_open_lab.mesh_guide_figures`、PNGは`node scripts/render_mesh_guides.cjs`。旧出力へは書き込まない。

## 保存した検証図版

`C:/Projects-GitHub/geoai-open-lab/projects/poi/data/cache/regional_mesh/kichijoji-v1/`のpopulation.svg/png、population_poi.svg/png、旧カバー、実行HTML、mesh500.csv、manifest.jsonは全て保持。必要なら応用節へ旧人口地図を掲載できる。旧HTMLは元の応用中心の構成であり、新記事本文とは構成が異なる。

既存のFoursquare-NOTICE.txt・Apache-LICENSE.txtと出典を維持。図版の署名は出典の代わりではない。生成物はGitへ追加しない。

## 役割分担・公式資料

記事1は方式選択、この記事は標準コードと階層、Notebook 12は人口・POI結合の応用検証。前のMAUPは区切りへの感度、駅周辺記事は用途別の範囲。次のEPSG記事は座標の基準と単位。

2026-10-23確認：[統計局の概要](https://www.stat.go.jp/data/mesh/m_tuite.html) / [区分図pp.1–6](https://www.stat.go.jp/data/mesh/pdf/m-kukaku.pdf) / [用語](https://www.stat.go.jp/data/mesh/yougo.html)。人口の定義・秘匿と再配布条件は[既存方法](regional-mesh.md)のe-Stat一次資料を使用する。

公開コード：[Notebook 12](https://github.com/isshiki/geoai-open-lab/blob/main/projects/poi/notebooks/12_regional_mesh.ipynb) / [既存実装](https://github.com/isshiki/geoai-open-lab/blob/main/projects/poi/src/geoai_open_lab/regional_mesh.py) / [追加階層補助](https://github.com/isshiki/geoai-open-lab/blob/main/projects/poi/src/geoai_open_lab/standard_mesh_guide.py)。
