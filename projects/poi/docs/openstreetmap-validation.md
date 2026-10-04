# OpenStreetMap 実データ検証

確認日: 2026-09-26。© OpenStreetMap contributors。データは[ODbL 1.0](https://www.openstreetmap.org/copyright)。本ページは取得条件と集計の記録で、生のPOI一覧は掲載しません。

## 環境と取得時点

- Python 3.14.0。osmnx 2.1.1 / geopandas 1.1.4 / shapely 2.1.2 / pyarrow 25.0.1 / pandas 3.0.6
- 取得開始UTC: 2026-09-26T06:59:22.578419+00:00
- 取得完了UTC: 2026-09-26T06:59:36.074247+00:00
- OSM base timestamp: 2026-09-26T06:57:36Z
- endpoint: [https://overpass-api.de/api/interpreter](https://overpass-api.de/api/interpreter)。APIキー・token・アカウント不要。
- AOI: kichijoji-station-bbox-v1 / EPSG:4326 / west=139.574, south=35.699, east=139.586, north=35.708。既存TOMLを使用。country=JPは設定値で、国フィルターは使用しない。
- 固定release / attic queryは使用していない。保存済み応答の再処理は可能だが、将来のAPI再取得で同一結果になる保証はない。
- 今回の最終再処理UTC: 2026-09-26T07:04:44.623776+00:00 — 2026-09-26T07:04:44.908553+00:00。cache_hit=True。

## queryと候補定義

amenity / shop / tourism / leisure / office / craft / healthcare / historic の8キーOR条件。node / way / relationを対象とする。件数LIMITなし。query全文はローカルmanifestに保存し、以下はそのまま転記した実行query。

```overpassql
[out:json][timeout:60][maxsize:67108864];((node['amenity'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(way['amenity'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(relation['amenity'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(node['shop'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(way['shop'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(relation['shop'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(node['tourism'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(way['tourism'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(relation['tourism'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(node['leisure'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(way['leisure'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(relation['leisure'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(node['office'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(way['office'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(relation['office'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(node['craft'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(way['craft'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(relation['craft'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(node['healthcare'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(way['healthcare'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(relation['healthcare'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(node['historic'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(way['historic'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;););(relation['historic'](poly:'35.699000 139.574000 35.699000 139.586000 35.708000 139.586000 35.708000 139.574000 35.699000 139.574000');(._;>;);););out;
```

OSM公式のPOI一覧ではなく本実験のPOI候補。再帰取得した構成要素もrawに含まれる。取得条件はgeometryがAOIと交差する全地物を必ず列挙する保証ではない。

## geometryと最終採用

| 段階 | 件数 |
| --- | ---: |
| OSMnx取得後（内部geometry処理・領域/tagフィルター後） | 1201 |
| geometry変換対象として採用 | 1201 |
| representative pointがAOI外 | 7 |
| 最終採用 | 1194 |
| 最終結果のAOI外代表点 | 0 |
| 重複した(osm_type, osm_id) | 0 |
| NULL / empty / invalid / unsupported geometry | 0 / 0 / 0 / 0 |

Pointは元座標、Polygon / MultiPolygonはrepresentative_point。境界を含むAOI判定で採用し、元geometryは保持する。AOIと交差する面をすべて採用する定義ではない。大きな面も代表点が外なら除外される。将来Point POIと比較しやすくする分析上の選択である。

OSMnxは先にNULL/empty除去とmake_valid等を行うため、上表の0件はrawに不正geometryがないことの証明ではない。重複IDはOSM要素キーの検査であり、同一実店舗の重複排除ではない。

- 最終osm_type: {"node": 1045, "way": 145, "relation": 4}
- 最終geometry: {"Point": 1045, "Polygon": 148, "MultiPolygon": 1}
- AOI最終判定前の面: 156件。最大面積は約200511 m²、AOIより大きい面は0件（EPSG:32654で計測）。面積による除外なし。

## relation照合

| 項目 | 件数 |
| --- | ---: |
| rawタグ一致relation | 7 |
| OSMnx geometry処理・領域フィルター後 | 6 |
| 最終正規化結果 | 4 |
| 未対応type | 1 |
| OSMnx後に存在しない | 1 |
| 対応typeだが不在・理由未特定 | 0 |
| rawから最終までの未対応または除外合計 | 3 |

- raw relation type: {"multipolygon": 6, "building": 1}
- type=buildingの1件はOSMnx 2.1.1の対応外。multipolygon 6件のうち2件は後段の代表点AOI判定で除外された。最終4件。OSMのrelationをすべてgeometry化できるとは説明しない。

## タグの実測

タグは複数同時に付くため、キー別件数の合計はPOI数ではない。以下は各キーの上位5値。全出現値はローカルmanifestに保存。

| キー | 出現数上位5値 |
| --- | --- |
| amenity | restaurant=157, parking=78, pub=77, fast_food=52, cafe=49 |
| shop | clothes=73, hairdresser=30, convenience=26, shoes=17, variety_store=16 |
| tourism | information=15, hotel=4, attraction=2, museum=1, gallery=1 |
| leisure | park=7, fitness_centre=5, sauna=2, pitch=2, amusement_arcade=2 |
| office | estate_agent=13, company=7, insurance=3, lawyer=1, financial=1 |
| craft | metal_construction=1, tailor=1 |
| healthcare | pharmacy=26, dentist=16, doctor=15, clinic=9, hospital=4 |
| historic | memorial=4, yes=1, wayside_shrine=1 |

## カフェと関連タグ

カフェは `amenity == 'cafe'` の完全一致で **49件**。店舗名検索や他データとの共通分類は行わない。OSMでこの条件を満たす候補数であり、実在する全カフェ店舗数ではない。

| key=value | 件数 |
| --- | ---: |
| amenity=cafe | 49 |
| amenity=internet_cafe | 4 |
| amenity=restaurant | 157 |
| amenity=fast_food | 52 |
| amenity=ice_cream | 1 |
| amenity=bar | 16 |
| amenity=pub | 77 |
| shop=coffee | 3 |

`cafe=yes` は今回取得・最終採用したPOI候補内で0件。8キーを持たないcafe=yesだけの地物はquery対象外。地域全体にcafe=yesがないという意味ではなく、追加queryは実施していない。

## 時間・保存サイズ・再現性

- 初回POST取得・JSON解析: 13.496秒（status確認は含まない）。
- 最終cache再処理: 0.285秒（GeoParquet保存時間を含まない）。
- 展開済みHTTP応答body: 516,468 bytes。
- 応答＋query＋取得時刻のcache JSON: 448,513 bytes。JSONを再serializeするためbody bytesとは異なる。
- places.parquet: 109,100 bytes。cafes.parquet: 23,856 bytes。
- 圧縮後の転送量・HTTPヘッダー込み通信量・サーバー側スキャン量は未観測。DuckDBは今回の取得経路で使わない。
- raw cache SHA-256: `264d638fb7a32b611f1e89ee852db6d07aa65a32781fa8be41c3ad07481dedbf`
- places SHA-256: `dd4ce1f1b62c23cfc2224534e54dc4596da01fe6bea8da5a728498c26373bdec`
- cafes SHA-256: `4de57f5cfc651e4bac5ae3b9f2fb002a53b2dd9970ffbfbe0b70c7a85e46dc09`

## 検証と実装上の発見

- 既存Foursquare / Overture 29件とOSM 13件の全42オフラインテストが成功。架空地物を使い、public Overpassには問い合わせない。
- 公開Notebookのコード7セルを全実行し、ローカルの実行済みNotebookとHTMLを生成。初回取得後の検証はcacheを利用。
- OSMnxが入力dictを変更するためコピーを渡し、raw relation照合の入力を保護。空のgeometry集合でも判定可能なよう真偽型を明示。
- raw / cache / GeoParquet / 実行済みNotebook / HTMLはdata以下にのみ保存。公開Notebookのoutput・execution_count・attachmentsは空。
- データの網羅性・正確性や他データとの優劣は評価していない。営業状態や実店舗の重複も評価していない。
- OSMnx private通信hookは2.1.1固定。将来更新時に再検証が必要。処理中のOSMnx設定変更があるため並列呼び出し非対応。

再現コマンド・利用条件は[実行手順](openstreetmap.md)を参照。
