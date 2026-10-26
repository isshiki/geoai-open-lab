# 都市機能影響の部分追試：出典と公開条件

確認日：2026-10-26。会社・顧客資産は使用しない。

- 論文：Qiu et al., Refined Identification of Urban Functional Areas Considering the Differentiated Spatial Influence of POIs—A Case Study of Changzhou, DOI [10.3390/ijgi15110482](https://www.mdpi.com/2220-9964/15/11/482)。ユーザー提供EPUB本文を読解。本文にCC BY 4.0表示。原文・図の転載はせず数式を実装する。ローカル本文・抽出テキストはGit管理外。
- 補足：本文記載の[公式S1/S2](https://www.mdpi.com/article/10.3390/ijgi15110482/s1)は2026-10-26時点、Web取得不可・通常HTTP接続403。存在しないとは判断しない。S1の重み・S2の閾値は未確認。
- POI：保存済みOverture 2026-09-23.0、`20261015T080101Z-tokyo`。sources/licenseを元Parquetに保持。[既存の出典・公開条件](region-feature-sources.md)を継承。生POI・派生CSV・地図はGit管理外。Foursquare NOTICEとApache LICENSEを成果物に同梱し加工日を記録。
- 駅：既存N02-25代表点、EPSG:6677、東西南北各2km。同じ出典資料を参照。
- 外部参照候補：[国土数値情報 都市地域土地利用細分メッシュ2021](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-L03-b-u-2021.html)。公式ページの許諾はCC BY 4.0（出典・変更表示の下で加工・再配布可）。5339、JGD2011、`L03-b-u-21_5339-jgd2011_GML.zip`、公式表示16.68MB。取得日時・URL・サイズ・SHA-256は取得後manifestへ記録。図には「国土数値情報（都市地域土地利用細分メッシュ2021）を加工」と表示。ZIPと切出し地物はGit管理外。2021年土地被覆と2026年POIの時点差、および公園・緑地とレクリエーション機能の意味の差がある。低層建物・高層建物を住宅や商業に決めつけない。

追加の住宅ハイブリッド・施設強度モデルは、適切な公開属性がない限り作らない。POI confidenceを施設規模や人気の代わりにしない。

土地利用の取得UTC：2026-10-26T08:27:41.096476+00:00、16,675,723 bytes、SHA-256 `f53b124d2ae83703db62c42a92d82f7db10886cf11ddb9a9f66afa176a2e4c39`。
[固定ZIPの公式配布URL](https://nlftp.mlit.go.jp/ksj/gml/data/L03-b-u/L03-b-u-21/L03-b-u-21_5339-jgd2011_GML.zip)。明示的な取得スクリプトは [acquire_urban_function_reference.py](../scripts/acquire_urban_function_reference.py)。再取得した内容が異なれば停止する。

[公式コード表](https://nlftp.mlit.go.jp/ksj/gml/codelist/LandUseCd-09-u.html)では、0703/0704は3階建以下の居住用建物のまとまりだが、0701は商業ビルとマンションの混在分類。低層住宅の補助資料には使えても住宅機能全体の完全な正解にはならない。今回の外部数値は1003だけの代理比較として固定した。
