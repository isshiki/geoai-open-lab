# Natural Earth：Notebook 14用データ条件

確認日：2026-10-24。データはNatural Earth Admin 0 Countries、1:110m。
公式配布ページ：https://www.naturalearthdata.com/downloads/110m-cultural-vectors/110m-admin-0-countries/
ページ記載：version 5.1.1、約210KB。配布URL：https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip
利用条件：https://www.naturalearthdata.com/about/terms-of-use/

Public domain。商用利用・改変・再配布可能、帰属表示は必須ではないが図にはMade with Natural Earthと明記する。生データはリポジトリ方針に従いGitへ入れない。世界の投影法比較用の低解像度境界であり、国土面積の公式値や国境の法的主張には使わない。de facto境界を含む。

ダウンロード時にZIP内VERSION・UTC・サイズ・SHA-256を記録し、版が異なる場合は採用を中止する。自動的に最新データへ追従しない。データはprojects/poi/data/raw/crs/natural-earth-5.1.1/へ保存する。既存POI・人口の追加取得はしない。

取得済み：2026-10-24T08:43:35.473574Z、214,976 bytes。SHA-256 `0f243aeac8ac6cf26f0417285b0bd33ac47f1b5bdb719fd3e0df37d03ea37110`。ZIP内VERSION=5.1.1を検査済み。取得スクリプトはこのhashも固定する。

再利用するOverture 2026-09-23.0は[既存の出典・利用条件](overture.md)に従う。保存済み入力のsourcesとライセンスを維持し、個別POIは公開しない。図のブログ掲載時もFoursquare由来Apache-2.0のNOTICE、著作権表示と変更日（今回加工2026-10-24）を維持する。駅は国土数値情報N02-25（CC BY 4.0）加工。Natural EarthのPublic domainをPOIや駅へ適用しない。
