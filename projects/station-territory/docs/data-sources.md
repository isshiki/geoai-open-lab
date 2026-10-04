# 入力と公開条件

確認日：2026-10-04。取得済みの公開データをローカルコピーして使用する。新規取得はファイル名・URL・サイズを提示してユーザー確認後に行う。

| 入力 | 固定版・提供元 | 利用条件・表示 |
| --- | --- | --- |
| OSM関東PBF | `kanto-261001.osm.pbf`。[Geofabrik](https://download.geofabrik.de/asia/japan/kanto.html) | [ODbL 1.0 / OSM著作権](https://www.openstreetmap.org/copyright)。© OpenStreetMap contributors |
| 駅 | `N02-25_GML.zip`。[N02 2025](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N02-2025.html) | CC BY 4.0。国土数値情報（鉄道データ）を加工と表示 |
| 行政区域 | `N03-20260101_{11,12,13,14}_GML.zip`。[N03 2026](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2026.html) | 提供条件と測量法上の二次利用手続を図表公開前に確認。国土数値情報（行政区域データ）を加工と表示 |
| 人口 | `tblT001142Q5339.zip`、2020年国勢調査、250m、JGD2011。[e-Stat配布](https://www.e-stat.go.jp/gis/statmap-search/data?statsId=T001142&code=5339&downloadType=2) | [e-Stat利用規約](https://www.e-stat.go.jp/terms-of-use)。総務省統計局「令和2年国勢調査に関する地域メッシュ統計」を加工と表示 |

JGD2011は測地系であり調査年ではない。2026-10-04の公式配布一覧確認では2025年250m人口メッシュは見つからず、既存2020年を採用した。市区町村単位の2025年公表をメッシュの公表と混同しない。

元取得UTC・URL・版は `data/reference/inventory.json` と `population-manifest.json`、ローカルコピーUTC・サイズ・SHA-256は `data/input-receipt.json` に保存する。元取得時刻をコピー時刻で上書きしない。原データ、格子、生成表、実行済みNotebook、HTMLはすべてGit管理外。

コードのApache-2.0は外部データへ適用しない。コード公開、図（Produced Work）の記事掲載、機械可読の派生データベースの公開は別に扱う。ODbL由来の派生表の提供条件とN03の二次利用手続は、実際の公開物を選んで確認する。現段階の図表はローカル確認用であり、再配布許諾確認済みとはしない。署名 `masahiko.info` はAttributionの代わりではない。
