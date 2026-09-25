# Overture Places 実データ検証

検証日: 2026-09-25。固定release `2026-09-23.0` / schema `v2.0.0`。
最終manifest（Git管理外）: `data/raw/overture/20260925T115558Z-2f21beb2/manifest.json`。
取得開始UTC: `2026-09-25T11:55:39.400149+00:00`、完了UTC: `2026-09-25T11:55:58.750623+00:00`。
Python 3.14.0 / DuckDB 1.5.5。拡張: [{"extension_name": "httpfs", "extension_version": "827222f"}, {"extension_name": "spatial", "extension_version": "eb1e57c"}]。

## 対象・取得

source: `s3://overturemaps-us-west-2/release/2026-09-23.0/theme=places/type=place/*`。
AOI: `configs/aoi/kichijoji.toml`、ID `kichijoji-station-bbox-v1`、EPSG:4326。
西 139.574 / 南 35.699 / 東 139.586 / 北 35.708。境界を含む。
国・営業状態・confidenceの事前フィルターなし、LIMITなし。

- bbox候補: 3,668件
- geometryの厳密な範囲判定後: **3,666件**
- カフェ相当: **202件**
- 取得処理時間（schema/EXPLAIN/候補取得/検査を含む、拡張準備と保存を除く）: 19.350秒
- places.parquet: 688,915 bytes
- cafes.parquet: 50,637 bytes

これは固定release・AOI・非NULLで有効なbboxに基づく取得結果です。実世界の全店舗の網羅性を保証しません。bboxがNULL/不正で候補に入らない世界全体の行は別途走査していません。

## 実行計画・負荷

EXPLAINのREAD_PARQUET内にbbox.xmin/xmax/ymin/ymaxの4条件と必要列のProjectionsを確認。計画上のpredicate pushdownを確認しました。表示された推定行数は実読取行数ではありません。
通信量・実スキャン量・ピークメモリは**未測定**。manifestではnull。保存サイズを通信量とは扱いません。全世界データのローカル保存は行っていませんが、転送量を計測していないので通信効率を定量的に実証したとは扱いません。

bbox候補のうち2件はgeometry座標が厳密なAOI外で除外されました。丸めを考慮してbbox重なりを候補条件にしていますが、この2件の差の原因を丸めと断定していません。

## geometry / ID

候補内のNULL/空/非Point geometry: 0。
採用POIのID重複: 0、geometryがbbox範囲外: 0。
全採用POIはgeometry座標によるAOI判定を満たします。

## スキーマ（DESCRIBE実測）

| column | type |
| --- | --- |
| id | VARCHAR |
| geometry | GEOMETRY('OGC:CRS84') |
| confidence | DOUBLE |
| websites | VARCHAR[] |
| emails | VARCHAR[] |
| socials | VARCHAR[] |
| phones | VARCHAR[] |
| brand | STRUCT(wikidata VARCHAR, "names" STRUCT("primary" VARCHAR, common MAP(VARCHAR, VARCHAR), rules STRUCT(variant VARCHAR, "language" VARCHAR, perspectives STRUCT("mode" VARCHAR, countries VARCHAR[]), "value" VARCHAR, "between" DOUBLE[], side VARCHAR)[])) |
| addresses | STRUCT(freeform VARCHAR, locality VARCHAR, postcode VARCHAR, region VARCHAR, country VARCHAR)[] |
| names | STRUCT("primary" VARCHAR, common MAP(VARCHAR, VARCHAR), rules STRUCT(variant VARCHAR, "language" VARCHAR, perspectives STRUCT("mode" VARCHAR, countries VARCHAR[]), "value" VARCHAR, "between" DOUBLE[], side VARCHAR)[]) |
| sources | STRUCT(property VARCHAR, dataset VARCHAR, license VARCHAR, record_id VARCHAR, update_time VARCHAR, confidence DOUBLE, "between" DOUBLE[], provider VARCHAR, resource VARCHAR, "version" VARCHAR)[] |
| operating_status | VARCHAR |
| basic_category | VARCHAR |
| taxonomy | STRUCT("primary" VARCHAR, hierarchy VARCHAR[], alternates VARCHAR[]) |
| version | INTEGER |
| bbox | STRUCT(xmin DOUBLE, xmax DOUBLE, ymin DOUBLE, ymax DOUBLE) |
| theme | VARCHAR |
| type | VARCHAR |

旧categoriesは存在しません。taxonomyはprimary / hierarchy / alternates。geometryはDuckDBでGEOMETRY型として読めます。実型はmanifestにも記録しています。

## basic_category / taxonomy

### basic_category上位10件

| value | count |
| --- | --- |
| restaurant | 797 |
| personal_or_beauty_service | 323 |
| bar | 264 |
| fashion_and_apparel_store | 243 |
| cafe | 147 |
| casual_eatery | 140 |
| shopping | 93 |
| food_and_beverage_store | 64 |
| wellness_service | 61 |
| specialty_school | 58 |

### taxonomy.primary上位10件

| value | count |
| --- | --- |
| japanese_restaurant | 403 |
| bar | 167 |
| cafe | 139 |
| hair_salon | 135 |
| clothing_store | 99 |
| shopping | 93 |
| restaurant | 84 |
| beauty_salon | 75 |
| NULL | 61 |
| italian_restaurant | 57 |

全出現カテゴリの件数表はmanifestに保存しています。カテゴリ品質の評価はしていません。

### NULL数・率

| field | null_count | null_percent |
| --- | --- | --- |
| basic_category | 55 | 1.5 |
| taxonomy | 61 | 1.664 |
| taxonomy_primary | 61 | 1.664 |
| taxonomy_hierarchy | 61 | 1.664 |
| taxonomy_alternates | 3629 | 98.991 |

primaryとhierarchy末尾の不一致: 0、非NULLのbasic_categoryが非NULL階層に含まれない件数: 0。NULLを分類確認済みとは扱いません。

## カフェ相当

basic_categoryがcafeまたはcoffee_shop。taxonomy.alternatesだけの一致は含めません。営業状態の除外なし。Internet CafeなどもOvertureの分類に従い含みます。

| value | count |
| --- | --- |
| cafe | 139 |
| coffee_shop | 55 |
| internet_cafe | 6 |
| hong_kong_style_cafe | 1 |
| NULL | 1 |

NULLの1件もbasic_categoryが条件に合うため含みます。現れなかったカテゴリを0件の行として追加していません。

## operating_status

全POI:

| value | count |
| --- | --- |
| NULL | 3665 |
| open | 1 |

カフェ相当:

| value | count |
| --- | --- |
| NULL | 202 |

permanently_closedは今回0件。ただしNULLは営業中を意味せず、202件を営業中のカフェ数とは書けません。状態フィルタ後の件数は今回の主結果として算出していません。

## confidence

| null_count | minimum | p25 | median | p75 | maximum |
| --- | --- | --- | --- | --- | --- |
| 0 | 0.04189654439687729 | 0.77 | 0.836222593486309 | 0.9711453318595886 | 1.0 |

提供元の存在への確信度スコアです。校正された確率や品質判定には使わず、独自閾値で除外していません。

## sources

| dataset | provider | license | source_entries |
| --- | --- | --- | --- |
| Overture | overture | CDLA-Permissive-2.0 | 3666 |
| meta | meta | CDLA-Permissive-2.0 | 2680 |
| Foursquare | foursquare | Apache-2.0 | 696 |
| Microsoft | microsoft | CDLA-Permissive-2.0 | 147 |
| AllThePlaces | alltheplaces | CC0-1.0 | 141 |
| PinMeTo | pinmeto | CDLA-Permissive-2.0 | 1 |
| DAC | dac | CDLA-Permissive-2.0 | 1 |

sources NULL: 0件。複数source要素あり: 3666件。Overture自身の要素を含むため、複数の独立した外部提供者が各POIを裏付けたことを意味しません。上表はsource要素数であり、POIの排他的な分類ではありません。Foursquare由来の一致分析は未実施です。

## 検証・公開安全性

- オフラインテスト29件成功（既存Foursquare 19件を含む）。境界、範囲外候補、NULL geometry、重複ID、スキーマ、カフェ、manifest、認証不要の接続設定を検査。
- 公開Notebook全8コードセルを上から実行成功。実行済みNotebookとHTMLはdata/cache/overture内に保存。
- 公開Notebookのoutput / execution_count / attachmentsは空。メタデータはカーネル情報のみ。
- 実行済みNotebookのエラーなしと出力内容を検査。HTML生成成功。ブラウザでの見た目の目視検査は未実施。
- data/raw、data/cache、実行済みHTML、.envはGit管理外。公開候補ファイルに設定済みtoken/API keyが含まれないことを検査。
- 上記は実装完了時点の検証記録です。公開後のコード版はGit履歴を参照してください。

## 公式資料と未確認事項

[利用手順](overture.md)に公式release notes・schema・taxonomy・ライセンス・STAC・Python clientの出典を記載。
Quickstartの旧categories.primaryやガイドのalternate単数形は採用していません。
本実験で示すのは取得・分類の動作確認です。網羅性、現況の正確性、他データとの優劣、独立性、Entity Resolutionは評価していません。
