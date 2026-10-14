# 駅中心1km四方：入力と公開条件

確認・加工日：2026-10-14。会社資産は使用しない。

## 駅代表点

国土交通省「国土数値情報（鉄道データ）」N02-25、基準日2025-12-31、JGD2011（EPSG:6668）。[公式説明](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N02-2025.html)にCC BY 4.0と記載。国土数値情報（鉄道データ）を加工、加工日と出典を図・文書に記載する。代表点という加工済み設定は利用条件に従い記録し、ZIPや駅線データはGitへ追加しない。

取得元：`https://nlftp.mlit.go.jp/ksj/gml/data/N02/N02-25/N02-25_GML.zip`。
既存保存ファイルは `projects/station-territory/data/raw/N02-25_GML.zip`。取得UTCは同テーマの公開データ受領記録にある `2026-10-03T09:28:23Z`、サイズ14,903,774 bytes、SHA-256 `aaf76af133b2e771e538fabc4646d2e443dc1d5a67b221382a28d744e706cc9f`。今回テーマ内dataへコピーし検証する。元テーマのコード・生成済み代表点は流用せず、公式ZIPから独立して算出する。

吉祥寺の公式N02_005gは003584、所属駅コードは003584（JR中央線）、003588（京王井の頭線）。同名だけで全国の駅をまとめない。公式グループコードに一致するN02_005cの線をEPSG:6677へ投影し、長さの中点を代表点とする。複数線なら結合し、非連結なら最長線（同長はWKT順）の中点を採用して監査する。これは駅出入口や徒歩アクセス地点ではなく、同一面積比較の中心。グループの代表コードが見つからなければ停止し、座標平均で補わない。

## Overture Places

releaseは2026-09-23.0、schema v2.0.0に固定。保存済み範囲が1km四方全体を覆わない場合のみ、同releaseの必要範囲をLIMITなしで取得する。公式公開S3を匿名で読む。場所の絞り込み用bboxと、正方形内の厳密な投影座標判定を分ける。sourcesを削除しない。

- [Places Guide](https://docs.overturemaps.org/guides/places/)
- [Attribution and Licensing](https://docs.overturemaps.org/attribution/)
- [Release Calendar](https://docs.overturemaps.org/release-calendar/)

PlacesにはCDLA-Permissive-2.0、Apache-2.0、CC0-1.0由来のデータがある。Foursquare由来はApache-2.0。Overture公式帰属表示の Copyright 2024 Foursquare Labs, Inc. All rights reserved. と、Overture schemaへの変換日 Changed: 2026-03-18 を保持する。[Foursquare NOTICE](https://opensource.foursquare.com/places-notice-txt/)は現在Copyright 2026と表示されるため両者を混同せず、確認時のNOTICE本文をローカル保存し、派生成果を渡す場合はNOTICE全文と[Apache License](../../../LICENSE)を併せる。本実験の抽出・格子集計の変更日は2026-10-14。元のsources/license情報は入力Parquetとmanifestに保持する。

Git公開物はコード・説明・集計値の記述。POI単位データ、ZIP、生成物は非公開のdataに保持する。将来集計済み特徴量・図・manifestを公開するときも、NOTICE・ライセンス・変更表示を同梱し、各sourceの条件を維持する。公式公開版は最大60日で消去されるため、同releaseの再取得可能性を保証しない。取得不能時は停止し、別releaseへ切り替えない。
