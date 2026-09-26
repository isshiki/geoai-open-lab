# OpenStreetMapのPOI候補を取得する

確認日: 2026-09-26。© OpenStreetMap contributors。
[OSM copyright](https://www.openstreetmap.org/copyright) / [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) / [Attribution Guidelines](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines)。OSMデータにはODbLが適用され、コードのApache-2.0とは別です。再配布には出典・ライセンスの表示、派生データベースには該当する継承・提供条件の確認が必要です。本実験はrawと正規化データをGit管理外に保存し、再配布しません。記事や成果物にもOSMの出典・ライセンスを表示します。

## 実験用定義

OSMに固定POIテーブルや単一taxonomyはありません。node / way / relationに付いたタグのうち、amenity / shop / tourism / leisure / office / craft / healthcare / historicの8キーのいずれかを持つ地物を候補とします。これは公式POI定義でも店舗だけの集合でもありません。公園や駐車場等も含み得ます。

Pointは元座標、Polygon / MultiPolygonは元geometryのrepresentative_pointで地点化します。元geometryをクリップせず保持し、代表点が既存吉祥寺AOI内（境界含む）のものだけを採用します。AOIにgeometryが交差する全地物を採用する定義ではなく、大きな面は代表点が外なら除外されます。将来Point POIと比較しやすくする今回の分析上の選択です。LineString等は未対応として数え、正規化結果から除外します。NULL/empty/invalidも別集計します。

カフェはamenity == 'cafe'の完全一致。internet_cafe、shop=coffee、restaurant等を自動的に含めません。cafe=yesは「今回取得した8キー条件のPOI候補内」での補足で、cafe=yes専用queryは行いません。

## 取得・保存

OSMnx 2.1.1を固定し、features_from_bboxでOverpass queryとgeometryを構築します。匿名のpublic Overpassを使用し、APIキー・token・アカウント不要。.envやcredentialを読みません。住所検索・Nominatimは使いません。

OSMnxのprivate通信関数だけを実行中に差し替え、応答と取得時刻を管理します。これは2.1.1に限定した実装で、他版では停止します。HTTPエラー・Overpass remark・不完全なJSONを成功としてcacheしません。public endpointのstatusを確認し、利用可能slotがなければ待ち続けず停止します。POSTは最大1回、自動リトライなし。小AOIでもquery分割が発生した場合は2回目を送らず停止します。成功応答はquery+endpointのハッシュで再利用し、別途取得する場合だけrefresh=Trueを指定します。

保存済みcacheからの再処理と、将来APIからの同一結果の再取得は別です。過去日時固定/atticは今回使用しません。元の取得UTCと再処理UTC、osm3s.timestamp_osm_base（なければnull）を分けます。raw JSONはdata/cache/osmに1部だけ保存し、正規化GeoParquet・カフェ・manifestはdata/raw/osmへ保存します。

OSMnxのrelation geometry対応はmultipolygon / boundaryです。rawにあるタグ一致relationと、OSMnx処理後・最終採用後を照合します。未対応と、領域フィルター等による除外を区別できない場合は理由未特定と記録します。OSMnx内部ではNULL/empty除去とmake_validが行われるため、後段の0件はraw段階の完全性保証ではありません。

## 公式資料

- [OSM Elements](https://wiki.openstreetmap.org/wiki/Elements)、[Tags](https://wiki.openstreetmap.org/wiki/Tags)
- [OSMnx API](https://osmnx.readthedocs.io/en/stable/user-reference.html)、[固定版実装](https://github.com/gboeing/osmnx/tree/v2.1.1/osmnx)
- [Overpass QL](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL)、[公共インスタンス利用](https://dev.overpass-api.de/overpass-doc/en/preface/commons.html)
- [amenity=cafe](https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dcafe)、[internet_cafe](https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dinternet_cafe)、[shop=coffee](https://wiki.openstreetmap.org/wiki/Tag:shop%3Dcoffee)
- [PointOnSurface](https://shapely.readthedocs.io/en/stable/reference/shapely.point_on_surface.html)
- 広域・反復取得には[Geofabrik PBF](https://download.geofabrik.de/)と[PyOsmium](https://docs.osmcode.org/pyosmium/latest/)が候補です。[DuckDB ST_ReadOSM](https://duckdb.org/docs/current/core_extensions/spatial/functions#st_readosm)はraw要素を読み、way/relationのgeometryは自動構築しません。今回は別方式を実装しません。

## 実行方法

リポジトリルートで実行します。既存のFoursquare / Overture用依存に加え、OSM用groupを指定します。

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD 'data/cache/uv'
$env:JUPYTER_CONFIG_DIR = Join-Path $PWD 'data/cache/jupyter/config'
$env:JUPYTER_DATA_DIR = Join-Path $PWD 'data/cache/jupyter/data'
$env:JUPYTER_RUNTIME_DIR = Join-Path $PWD 'data/cache/jupyter/runtime'
$env:IPYTHONDIR = Join-Path $PWD 'data/cache/ipython'
uv sync --locked --group notebooks --group osm
uv run --locked --group notebooks --group osm jupyter lab notebooks/03_openstreetmap_poi.ipynb
```

全セル実行とHTML生成、全テストは次のコマンドです。

```powershell
uv run --locked --group notebooks --group osm python -m unittest discover -s tests -q
uv run --locked --group notebooks --group osm jupyter nbconvert --execute --to notebook notebooks/03_openstreetmap_poi.ipynb --output 03_openstreetmap_poi.executed --output-dir data/cache/osm --ExecutePreprocessor.timeout=240
uv run --locked --group notebooks --group osm jupyter nbconvert --to html data/cache/osm/03_openstreetmap_poi.executed.ipynb --output-dir data/cache/osm
```

公開Notebookは出力・実行番号・attachmentsを空に保ちます。実行済みNotebook / HTMLはローカル確認専用です。manifestにはOSMnx実バージョン、Python・主要package、query、取得日時、OSM base timestamp、応答と出力のSHA-256・サイズ、コードとlockfileのSHA-256を保存します。AOIのcountry=JPは設定メタデータで、Overpassの国フィルターや国境照合は行いません。

取得上限は小AOI（4 km²以下）、query timeout=60秒、Overpass maxsize=64 MiB、受信body上限64 MiBです。HTTP接続timeout=10秒・読み取りtimeout=90秒、受信chunk間で経過120秒を超えると中断します。これは処理全体の厳密な120秒上限ではありません。初回失敗時は原因を確認し、時間をおいて手動で再実行してください。

通常の再実行は同一queryの初回成功cacheを読みます。`refresh=True`は明示的な追加問い合わせなので慎重に使用してください。新応答は別名に保存し、初回cacheを上書きしません。refresh後も通常実行は初回cacheを選ぶ仕様です。空の結果や未対応データでOSMnxが例外を返した場合、raw cacheは残りますが正常終了manifestは作成しません。

OSMnxがgeometry生成時に応答dictを書き換えるため、保存済み応答のコピーを渡します。relation照合には元の応答を使います。再帰取得された構成要素もrawに含まれるため、rawタグ一致数はAOI採用数と同義ではありません。通信量全体、圧縮転送量、サーバー側スキャン量は計測していません。body bytesは展開済み応答のサイズです。

実測値・制約は[検証記録](openstreetmap-validation.md)を参照してください。
