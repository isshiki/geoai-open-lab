# 駅周辺の範囲定義（Notebook 11）

吉祥寺のみ。既存の駅代表点、Overture 2026-09-23.0、EPSG:6677を固定し、1km四方・半径500m・徒歩5分/10分を比較する。既存Notebook 09/10と既存結果は変更しない。[検証・記事資料](walking-range-article-handoff.md)。

## 入力と出典

### 固定OSM道路網

[Geofabrik関東](https://download.geofabrik.de/asia/japan/kanto.html)の`kanto-261001.osm.pbf`（2026-10-01版）、515,684,430 bytes。元プロジェクトの取得記録UTCは2026-10-03T09:29:33Z。ファイル名の版を記録しており、PBF内部のデータ基準時刻は別途抽出していない。

SHA-256: `5e0b1bec8d8754a18db3950c6a39e4921e8c19069106a1ac038731f3d250ca83`。

ユーザー指定の公開個人プロジェクト[eki-walk](https://github.com/isshiki/eki-walk)の作成済み道路網を読み取り専用で再利用。元PBFと道路2ファイルの実ハッシュを照合した。元プロジェクトは編集していない。初回インポート日時・部分キャッシュのハッシュもmanifestに保存。

| ファイル | 行数 | SHA-256 |
| --- | ---: | --- |
| nodes.parquet | 3,466,737 | `48cbab547e9f7b87453e44044c904b5ba56b5aefa15e37a1de6db22bea45dd01` |
| edges.parquet | 4,035,109 | `a95533cd09652be977924af23b8d969afef02f03dfa1c15e1f163b8080de8fd1` |

**u/vはOSMノードIDではなくnodesの行番号**。行番号を座標・IDへ対応付ける。上流は連続OSMノード間の線分長をEPSG:6677で計算する。保存length_mと座標からの再計算を全辺で照合した。図は道路ノード間の概略線であり、道路幅・歩道の細部・屋内経路を再現するものではない。

上流の固定依存は[rail-gap-map@4176263 network.py](https://github.com/isshiki/rail-gap-map/blob/4176263/src/ekiwalk/network.py)と[osmtags.py](https://github.com/isshiki/rail-gap-map/blob/4176263/src/ekiwalk/osmtags.py)。eki-walkにインストール済みの実装も確認した。コードは移植せず、生成済み入力のみを使う。

- highwayなし、area=yes、foot=noを除外。
- highwayがmotorway / motorway_link / construction / proposed / abandoned / razed / raceway / bus_guideway / escapeなら除外。
- motorroad=yes、またはaccess=no/privateは、foot=yes/designated/permissiveなら許容、それ以外は除外。
- 東京計算用bbox `[138.90, 35.47, 140.00, 35.93]` 内の道路を作り、最大連結成分のみを保存。双方向、同一端点の重複辺は1本。交差して見えるだけでは接続しない。
- cycleway・階段なども上記規則を満たせば含む。**OSMnxのwalkフィルターと同一ではない**。自動車一方通行は用いず、歩行固有の方向・時間帯・バリア制約は扱わない。

### POIと駅

既存`data/raw/similar_regions/20261015T080101Z-tokyo/`を再利用。Overture release `2026-09-23.0`、取得UTC `2026-10-15T08:01:26.347545+00:00`、全531,156行。入力manifestのSHA-256・件数・LIMITなし・各種フィルターなし・取得範囲を照合する。

駅は`configs/aoi/kichijoji_station_1km.toml`。N02-25の既存代表点（EPSG:6677でx=-22941.702420628444、y=-32905.06120966877）であり、出口ではない。[既存の出典・駅統合規則](region-feature-sources.md)を維持する。

## 計算条件

1. POI候補は駅中心±1000m。必要範囲が既存取得範囲に含まれることを検査し、未取得を0件にしない。
2. 道路は駅中心±1100m矩形と線分bboxが交差する辺を切らずに保存。部分キャッシュは4,618ノード・5,846辺。正の長さの辺を使う。元全域の長さ0の3辺は候補範囲外で、今回の接続に影響しない。
3. 駅代表点と各POIを最も近い辺へ投影。同距離は端点ID順。接続上限100m。駅へ到達できる別の辺へ飛ばさず、非到達成分も区別する。
4. 駅側接続＋道路上の最短距離＋POI側接続で判定。同一辺上では端点まで迂回させない。接続線は入口の確認を伴わない直線近似。
5. 80m/分、5分400m、10分800m。待ち時間・階段の負荷・坂・改札・混雑を含まない。OSMに通路があれば辺として使うが屋内アクセスは保証しない。
6. 円はEPSG:6677の直線距離≤500m、正方形はx/y差の絶対値≤500m。境界を含める。各条件内では1IDを1回数え、条件間の重複は許容する。
7. 道路総延長は到達できる辺の部分区間を合併して合計。往復・重複区間を二重計上せず、接続線は含めない。徒歩圏ポリゴンは作らず、bufferやconvex hullによる面積判定はしない。

線分長が座標上の距離であることを照合しているため、総距離800m以内の経路は直線距離でも800m以内に収まる。±1100mはその全経路に加え、候補POI±1000mと100mの接続に十分な範囲。到達線の端が抽出境界に触れないことも確認する。この幾何学的な確認は、OSM自体に道路欠落がないことの保証ではない。

6カテゴリは`configs/region_features.toml`を再利用。食事=restaurant/casual_eatery、カフェ=cafe/coffee_shop、バー=bar、衣料=fashion_and_apparel_store、美容等=personal_or_beauty_service、食品小売=food_and_beverage_store。primary等ではなく保存済みbasic_categoryを用いる。その他と欠損を分け、分母は各条件の全POI登録数。営業状態で除外しない。

## 再実行

`projects/poi`で既存uv環境を使う。依存追加・ダウンロードなし。主計算はNetworkX、Shapely、PyProjを使用する。今回OSMnxによる道路取得は行わない。

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD 'data/cache/uv'
uv sync --locked --offline --group osm --group clustering --group notebooks
# 初回のみ、手元の検証済み入力の場所を指定する（自動取得しない）
uv run --no-sync python -m geoai_open_lab.walking_range --road-dir <道路ディレクトリ> --osm-pbf <元PBF>
# 以降は部分キャッシュだけで実行
uv run --no-sync python -m geoai_open_lab.walking_range
uv run --no-sync python scripts/execute_walking_notebook.py
node scripts/render_walking.cjs
```

初回入力は環境変数`GEOAI_OSM_ROAD_DIR` / `GEOAI_OSM_PBF`でも指定できる。環境変数・CLIの値を公開物へ記録しない。入力ハッシュが異なる場合は停止し、別版へ自動切替しない。PNG描画は既存Playwrightとブラウザが必要で、スクリプトはインストールや外部通信を行わない。`BROWSER_EXECUTABLE`で既存ブラウザを指定可能。

固定キャッシュは`data/cache/walking_range/roads-20261001/`、結果は`data/cache/walking_range/kichijoji-v1/`。生データ、対応表、実行済みNotebook/HTML、図はGit管理外。公開Notebookは出力なし。

## 利用条件・限界

確認日2026-10-22。OSMは[ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/)。図に`© OpenStreetMap contributors`、ODbL、[copyright URL](https://www.openstreetmap.org/copyright)を表示。派生DBの公開には継承・提供義務がある。図の公開でも帰属表示だけで全義務が消えるとは解釈しない。今回Gitへ公開するのはコード・手順・集約した検証記録で、道路DBとPOI対応表は公開しない。図をブログ公開する際は[ODbL 4.6](https://opendatacommons.org/licenses/odbl/1-0/)に照らし、必要な派生DBまたは再構成方法の提供方法も確認する。

Overtureは[既存条件](overture.md)に従い、Foursquare由来のApache 2.0、NOTICE、変更表示を維持。駅はN02-25、CC BY 4.0。リポジトリのApache 2.0が外部データに適用されるわけではない。

固定スナップショットにした理由は、ライブAPI障害の回避だけでなく、同じ道路を用いた再現性確保。Overpassはstatus確認で502・タイムアウト等となり、道路取得は成功していない。障害原因は未確認で、PHP関連障害との因果関係は断定しない。ライブAPIは今回の主経路から外した。

駅勢圏・商圏の唯一の正解ではない。接続線が線路や建物などを横切る可能性、最大成分以外の道の除外、道路・POIの欠落と時点差がある。売上・需要・出店可否・住みやすさは判断せず、吉祥寺1駅から他地域へ一般化しない。
