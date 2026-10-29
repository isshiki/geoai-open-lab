# GeoJSONをPythonで扱う　読み込み・作成・検証・地図表示

記事は未執筆・未公開。前編「GeoJSON入門　JSONで地図の点・線・面を表す仕組み」で理解した構造を、Pythonで動かす後編です。[Notebook 15](../notebooks/15_geojson.ipynb) / [実装](../src/geoai_open_lab/geojson_tutorial.py) / [検証記録](geojson-python-validation.md)。

## 初心者向けのストーリー

1. 東京駅付近を想定した3つの架空地物を用意する。Point、LineString、Polygonを1つのFeatureCollectionに格納。
2. jsonで読むと辞書、GeoPandasで読むと地理データの表になる。Featureは1行、propertiesは属性列、geometryは形状列。
3. Shapelyで作り、WGS 84の経度・緯度で保存する。再読込して形状と属性を照合。
4. 「読めた＝正しい」ではない。JSON構文、基本構造、幾何学的妥当性、内容の4段階で確かめる。
5. 最後に地図で位置と名前を確認する。図に表示できても実在する経路・施設境界だとは限らない。

データはすべて本プロジェクトで作った説明用の架空データ。外部データセットや背景タイルは取得していません。例の地点も測量済みの駅代表点ではありません。オリジナルのコード・説明はリポジトリのApache-2.0、生成ファイルはGit管理外です。

## 実測環境（2026-10-29）

既存uv環境：Python 3.14.0、GeoPandas 1.1.4、Shapely 2.1.2、GEOS 3.13.1、pyogrio 0.13.0、GDAL 3.12.4、pandas 3.0.6、pyproj 3.8.0、nbclient 0.11.0。追加依存・lockfile変更なし。公式Webのstable文書はインストール版より新しい場合があるため、以下の挙動はこの環境の実測として記載します。

## 掲載コード候補

作業場所は `projects/poi/`。初回環境構築は `uv sync --locked --group osm --group notebooks`。既存環境の再実行はネット取得不要です。

### jsonで読み込む

```python
import json
from geoai_open_lab.geojson_tutorial import example_collection

data = json.loads(json.dumps(example_collection(), ensure_ascii=False))
print(data['type'], len(data['features']))  # FeatureCollection 3
for feature in data['features']:
    print(feature['geometry']['type'], feature['properties']['name'])
```

ファイルがある場合は `with open(path, encoding='utf-8') as f: data = json.load(f)`。jsonはGeoJSONの構造や座標を検証しません。既定のPython jsonはNaN/Infinityも受け入れるため、厳密なJSON検査器とも言い切らないでください。実装のstrict_loadsは非標準の数値定数を拒否する補助です。

### GeoDataFrameへ変換する

```python
import geopandas as gpd
gdf = gpd.GeoDataFrame.from_features(data, crs='EPSG:4326')
print(gdf.geom_type)
print(gdf[['name', 'fictional']])
```

ここでcrsを設定できるのは、元データがWGS 84経緯度と分かっているため。CRSの指定だけでは座標値は変わりません。GeoJSONの座標順は経度、緯度です。EPSGの軸記述と混同しないでください。

### Shapelyで作成して保存する

```python
from pathlib import Path
from shapely.geometry import Point, LineString, Polygon
from shapely.geometry.polygon import orient

shapes = [
    Point(139.767, 35.681),
    LineString([(139.764, 35.679), (139.766, 35.680), (139.770, 35.682)]),
    orient(Polygon([(139.768, 35.678), (139.772, 35.678),
                    (139.772, 35.680), (139.768, 35.680)]), sign=1),
]
created = gpd.GeoDataFrame(
    {'name': ['説明用の地点', '説明用の移動線', '説明用の範囲']},
    geometry=shapes, crs='EPSG:4326')
path = Path('data/cache/geojson/python-v1/article_example.geojson')
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(created.to_json(to_wgs84=True, drop_id=True,
                               ensure_ascii=False, allow_nan=False), encoding='utf-8')
loaded = gpd.read_file(path, engine='pyogrio')
assert all(a.equals_exact(b, 0) for a, b in zip(created.geometry, loaded.geometry))
assert created['name'].equals(loaded['name'])
```

ShapelyのPolygonコンストラクタは末尾の座標を補いますが、GeoJSONの原文では閉鎖座標が必要です。外周は反時計回り、穴は時計回りがRFCの規則。向きが異なるだけで読込拒否するとは限りません。`to_wgs84=True`だけで向き・自己交差・内容まで正しくなるわけではありません。任意のJSON全体のバイト一致ではなく、今回の形状と単純な属性の保持を確認しています。

## 誤り例の実測

「is_valid」はShapelyのshape()で生成した後の地物の値。—は前段の失敗により未評価です。

| 例 | json | from_features | read_file（pyogrio） | is_valid | 簡易基本チェック | 内容チェック |
|---|---|---|---|---|---|---|
| 正常3地物 | 成功 | 成功 | 成功 | 全True | 通過 | 通過 |
| カンマ不足 | 失敗 | — | 失敗 | — | — | — |
| 東京の経緯度逆転 | 成功 | 成功 | 成功 | 全True | 緯度の数値範囲で検出 | 想定地域外 |
| Polygon未閉鎖 | 成功 | 成功・閉鎖座標を補完 | GEOSException | 補完後True | 元の未閉鎖を検出 | 通過 |
| 自己交差Polygon | 成功 | 成功 | 成功 | PolygonはFalse | 通過 | 通過 |
| 数値範囲内だが別の場所 | 成功 | 成功 | 成功 | 全True | 通過 | 想定地域外 |
| featuresが配列ではない | 成功 | 失敗 | 失敗 | — | 構造で検出 | 評価不能 |

経緯度逆転は今回、緯度139.767度となるため範囲チェックで検出できました。両方が有効範囲に収まる場合はこの検査だけでは検出できません。想定地域内の架空の線や境界の実在性も検出できません。自己交差は基本構造とは別に `gdf.is_valid` / `shapely.is_valid_reason()` で調べます。

簡易関数basic_checkは非nullの2D Point/LineString/Polygonを持つFeatureCollection専用です。完全なRFC 7946検証器ではありません。RFCで有効なnull geometry、Multi系、GeometryCollection、3Dなども、このチュートリアルでは対象外として返します。JSON Schemaの完全検証・属性の意味・日付変更線は扱いません。

## 保存方法によるcrsの違い

| 方法 | crsメンバー | 座標 |
|---|---|---|
| WGS 84のto_json既定値 | なし | 経度・緯度 |
| EPSG:6677のto_json既定値 | あり（6677） | 投影座標のまま |
| EPSG:6677のto_json(to_wgs84=True) | なし | WGS 84へ変換 |
| WGS 84のto_file既定値、pyogrio | あり（CRS84） | 経度・緯度 |
| to_file(..., RFC7946='YES')、pyogrio | なし | 経度・緯度 |

RFC 7946では旧GeoJSONのcrs指定で別座標系へ切り替える方式を紹介しません。エンジンとバージョンを明記し、書き出したJSONそのものを確認します。RFC7946オプションはGDALのGeoJSONドライバのオプションです。一般的な形状修復や現実の正しさの保証ではありません。

## 図版・実行結果

保存先：`projects/poi/data/cache/geojson/python-v1/`。全図1600×900のSVG/PNG、同名 `_preview_800.png` も作成。署名はタイトル右上、白地・淡いカード、点は青・線は橙・面は緑で統一。表示座標系はEPSG:6677、基図なし。

| ファイル（SVG / 同名PNG） | キャプション・alt案 |
|---|---|
| cover_1600x900.svg | GeoJSONを読み、作り、検証して点・線・面を表示するPython入門 |
| reading_flow.svg | ファイルを辞書として読み、地理データの表へ変換して保存・再読込する流れ |
| dataframe.svg | 3つのFeatureが3行になり、geometryとpropertiesが表の列へ対応する |
| validation_layers.svg | JSON構文・基本構造・幾何・内容という4段階の検証 |
| error_examples.svg | 読込成功とis_validが意味する範囲は異なる。未閉鎖Polygonは読込経路で結果が違う |
| final_map.svg | 東京駅付近を想定した架空の点・移動線・範囲。実在の経路・境界ではない |

実行済みNotebookは `15_geojson.executed.ipynb`、HTMLは `15_geojson.html`。実測表は `results.json`、`validation.csv`、`exports.csv`。正常例 `example.geojson` と各誤り例も生成物として保存し、Gitへは追加しません。

```powershell
uv --cache-dir data/cache/uv run --no-sync python -m geoai_open_lab.geojson_tutorial
uv --cache-dir data/cache/uv run --no-sync python scripts/execute_geojson_notebook.py
node scripts/render_geojson.cjs
```

PNGレンダラは既存PlaywrightとEdgeを利用し、HTTP通信を遮断します。NodeのPlaywright解決パスを環境のNODE_PATH、ブラウザをBROWSER_EXECUTABLEへ指定できます。分析の実行にPNGレンダラは不要です。

## 前後編のつなぎ方

前編末尾：「次は、点・線・面をPythonで読み込み、作成・保存・検証して地図へ表示します。」後編導入：「前編で見たFeatureCollectionを、今回はPythonの辞書とGeoDataFrameとして扱います。」前編URLは未指定のため記事側で実URLを設定してください。

## 公式出典・注意点

確認日2026-10-29。仕様と実測を区別します。外部データ・図の転載はありません。

- [RFC 7946](https://www.rfc-editor.org/rfc/rfc7946)：§3の構造、§3.1.1座標順、§3.1.6閉鎖と向き、§4のWGS 84。crsで投影座標を宣言する旧方式を現行仕様として扱わない。
- [GeoPandas from_features](https://geopandas.org/en/stable/docs/reference/api/geopandas.GeoDataFrame.from_features.html)、[to_json](https://geopandas.org/en/stable/docs/reference/api/geopandas.GeoDataFrame.to_json.html)、[to_file](https://geopandas.org/en/stable/docs/reference/api/geopandas.GeoDataFrame.to_file.html)：表への変換と保存オプション。
- [Shapely is_valid](https://shapely.readthedocs.io/en/stable/reference/shapely.is_valid.html)、[Polygonの説明](https://shapely.readthedocs.io/en/stable/manual.html#polygons)：幾何学的な検査と生成。Shapelyは地理座標の意味や実在性を検査しない。
- [GDAL GeoJSONドライバ](https://gdal.org/en/stable/drivers/vector/geojson.html)：RFC7946書出しオプション。
- [Python json](https://docs.python.org/3/library/json.html)：構文読込と非標準数値の扱い。

大容量処理、Multi系、穴、反日付変更線、高さ、属性型の複雑な往復は対象外。距離・面積を緯度経度の度で計算せず、[座標系の記事資料](crs-article-handoff.md)へ誘導します。自動補完を便利な万能修復として勧めず、元データを検査してから変換する順番を伝えてください。
