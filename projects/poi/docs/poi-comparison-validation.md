# POI比較の実データ検証記録

[利用ガイド](poi-comparison.md) / [Notebook 04](../notebooks/04_poi_comparison.ipynb)

最終コードによるNotebook全セル実行の集計です。生データ・対応表・手動確認CSVはGit管理外です。
高信頼はルール上の一致候補であり、正解確認済みの実店舗ではありません。accuracy / coverage / 優劣は評価しません。

## 実行と入力

- comparison run: `20260927T151520Z-8fc00baf`
- 比較開始UTC: `2026-09-27T15:15:20.395397+00:00`
- 比較終了UTC: `2026-09-27T15:20:01.467607+00:00`
- 検証時コード: `cb81525`を基点とする未コミット差分。実行manifestにコード・Notebook・lockfileのSHA-256を保存。
- AOI: west=139.574, south=35.699, east=139.586, north=35.708。既存TOMLを再利用、境界を含む。
- Foursquareはcountry=JP。Overture・OSMは既存取得定義を維持。営業状態による共通filterなし。

| Provider | snapshot / release / base timestamp | 元データ取得開始UTC | 元データ取得終了UTC |
| --- | --- | --- | --- |
| foursquare | Places `2325979374271449319` / Categories `5006175908264532092` | 2026-09-27T14:53:02.420039+00:00 | 2026-09-27T14:53:47.702170+00:00 |
| overture | `2026-09-23.0` | 2026-09-25T11:55:39.400149+00:00 | 2026-09-25T11:55:58.750623+00:00 |
| osm | `2026-09-26T06:57:36Z` | 2026-09-26T06:59:22.578419+00:00 | 2026-09-26T06:59:36.074247+00:00 |

Foursquare全件取得は今回新規に実行し、Notebook実行では完成済み結果を再利用しました。
Overture / OSMは保存済み結果を再利用し、新規取得・Overpass再問い合わせは行っていません。
入力ファイル・OSM raw応答のhashとAOI・件数を検証しました。3データは同時刻のsnapshotではありません。

| Runtime | Version |
| --- | --- |
| python | 3.14.0 |
| duckdb | 1.5.5 |
| pandas | 3.0.6 |
| pyarrow | 25.0.1 |
| shapely | 2.1.2 |
| pyproj | 3.8.0 |
| osmnx | 2.1.1 |

## Foursquare全件取得のハードゲート

| 項目 | 結果 |
| --- | --- |
| `count_query` | 7176 |
| `retrieved_rows` | 7176 |
| `unique_ids` | 7176 |
| `duplicate_ids` | 0 |
| `null_geometry` | 0 |
| `invalid_coordinates` | 0 |
| `outside_aoi` | 0 |
| `wrong_country` | 0 |
| `schema_valid` | True |
| `unmatched_category_ids` | 0 |
| `categories_count` | 1279 |
| `saved_rows` | 7176 |
| `full_aoi_gate_passed` | True |

同一snapshot・同一country/bboxの独立したCOUNT、LIMITなし取得、unique ID、保存後の件数が一致しました。
取得対象行のID、座標、geometry非NULL、country、schema、Categories整合性を検証しています。
NULL座標はbbox条件を満たせないため、これは全世界のNULL座標件数の調査ではありません。
旧500件サンプルとNotebook 01の挙動は変更していません。今回の全件も、固定条件を満たすレコード全件という意味です。

## 件数と属性presence

| Provider | 対象レコード数 |
| --- | --- |
| foursquare | 7,176 |
| overture | 3,666 |
| osm | 1,194 |

分母は各providerの取得全レコードです。値がない行を除外しません。
住所は国コード以外の成分が1つでもあれば値ありとし、市名だけの場合も含みます。
phone / websiteは非空の値の存在です。有効性や最新性、完全な住所の割合ではありません。

| 属性 | Foursquare 件数（%） | Overture 件数（%） | OSM 件数（%） |
| --- | --- | --- | --- |
| name | 7,176 (100.0%) | 3,666 (100.0%) | 958 (80.2%) |
| address | 6,847 (95.4%) | 3,655 (99.7%) | 142 (11.9%) |
| phone | 4,556 (63.5%) | 3,215 (87.7%) | 93 (7.8%) |
| website | 2,557 (35.6%) | 2,860 (78.0%) | 141 (11.8%) |
| category | 7,022 (97.9%) | 3,611 (98.5%) | 1,194 (100.0%) |
| brand | N/A | 439 (12.0%) | 255 (21.4%) |

Foursquareのbrandはschema上の取得対象ではないためN/Aです。カテゴリ共通化はしていません。
OSMは8キーOR条件で抽出しているためcategory presence 100%は取得条件に由来します。
OSM住所は採用済み1,194 IDにのみraw応答から補完し、presenceは128件から142件へ増えました。
比較行の追加・削除はなく、raw構成要素も混入していません。

## 距離分布と閾値

名前はNFKC / strip / 連続空白統一 / lowercaseのみ。元名称、語、記号を保持し、空名称同士は一致しません。
EPSG:4326からEPSG:32654へ投影。Shapely STRtreeで候補距離内の全候補を列挙します。
以下は非空の正規化名が完全一致するAOI内の候補ペア全体です。確定した同一店舗の位置誤差ではありません。
名前で先に候補を絞って100m超も調べています。100m超の組を採用する意味ではありません。

| 距離 | FSQ–Overture | FSQ–OSM | Overture–OSM |
| --- | --- | --- | --- |
| 0～5m | 993 | 87 | 64 |
| 5m超～10m | 248 | 84 | 56 |
| 10m超～20m | 208 | 76 | 55 |
| 20m超～30m | 54 | 25 | 15 |
| 30m超～50m | 58 | 18 | 10 |
| 50m超～100m | 34 | 14 | 9 |
| 100m超 | 147 | 97 | 100 |

**正式採用: 候補探索100m、自動採用30m。**
100m以内の完全一致候補のうち30m以内の割合はFSQ–Overture約94.2%、FSQ–OSM約89.5%、Overture–OSM約90.9%。
3ペアとも近距離に多く、30m超にも候補があります。探索を100mまで広げて競合を見つけつつ、
30m超は自動採用しない保守的な初期設定を維持します。正解データに対する最適化や精度保証ではありません。

次は探索半径の感度です。自動採用距離は30mに固定しています。競合ペア数は要確認候補のうち強い競合を持つ組で、
同名競合ID数は左右別です。同じレコードに複数の候補があるためペア数とレコード数は異なります。

| Pair | 探索m | 全空間候補 | 名前完全一致 | 高信頼(auto30m) | 要確認 | 競合ペア | 同名競合ID 左/右 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| foursquare_overture | 30 | 229,136 | 1503 | 1358 | 14,113 | 113 | 2/6 |
| foursquare_overture | 50 | 553,120 | 1561 | 1357 | 19,245 | 247 | 2/8 |
| foursquare_overture | 100 | 1,993,230 | 1595 | 1354 | 27,252 | 639 | 2/12 |
| foursquare_osm | 30 | 69,830 | 272 | 250 | 158 | 15 | 4/2 |
| foursquare_osm | 50 | 179,819 | 290 | 249 | 188 | 17 | 5/2 |
| foursquare_osm | 100 | 659,788 | 304 | 244 | 225 | 29 | 10/6 |
| overture_osm | 30 | 34,059 | 190 | 180 | 102 | 3 | 1/0 |
| overture_osm | 50 | 86,515 | 200 | 180 | 120 | 3 | 1/0 |
| overture_osm | 100 | 310,928 | 209 | 178 | 142 | 10 | 3/1 |

強い競合は非空の同名または対称SequenceMatcher類似度0.90以上です。
共通ドメインや同じ建物住所だけでは強い競合とせず、補助情報のみの一致は要確認に残します。
電話・hostname・比較可能な7桁郵便番号の明確な不一致は高信頼を止めます。
住所の表記差や比較不能な郵便番号を矛盾として断定しません。類似度0.90は要確認探索用の暫定値です。

## Pairwise / unmatched / three-way

| Pair | 空間候補ペア | 高信頼候補 | 要確認ペア |
| --- | --- | --- | --- |
| foursquare_overture | 1,993,230 | 1,354 | 27,252 |
| foursquare_osm | 659,788 | 244 | 225 |
| overture_osm | 310,928 | 178 | 142 |

高信頼は非空の正規化名完全一致、30m以内、双方で一意、強い競合なし、明確な補助属性矛盾なし、の組だけです。
補助属性一致だけによる昇格、近い順・ID順のtie break、最大マッチ数の最適化は行いません。
各pairの採用結果で左右のID重複がないことを検証しました。

| Pair | Provider | 空間候補なし | 近接あり・名称等の根拠不足 | 要確認あり | 名称欠損等の根拠不足 |
| --- | --- | --- | --- | --- | --- |
| foursquare_overture | foursquare | 0 | 2551 | 3271 | 0 |
| foursquare_overture | overture | 0 | 821 | 1491 | 0 |
| foursquare_osm | foursquare | 12 | 6711 | 209 | 0 |
| foursquare_osm | osm | 0 | 546 | 169 | 235 |
| overture_osm | overture | 8 | 3349 | 131 | 0 |
| overture_osm | osm | 0 | 670 | 111 | 235 |

各方向で「高信頼で対応したレコード数＋上の4分類」が取得件数に一致することを検証しました。
要確認ペアには、別の組で高信頼採用されたレコードに接続する弱い候補もあり得ます。

**three-wayは102組。** 3辺すべてが高信頼の三角形だけを採用し、各provider 1件ずつを検証しました。
2辺の連鎖は自動統合しません。

| Provider | 他のどちらにも高信頼の対応が得られなかったレコード数 |
| --- | --- |
| foursquare | 5,681 |
| overture | 2,236 |
| osm | 888 |

これは「そのデータだけに存在する」「他データに存在しない」という証明ではありません。

## OvertureのFoursquare source監査

Overture 3,666 POI中、Foursquare sourceを持つものは696件です。
このフラグをcandidate生成・matching判定へ渡していないことをテストしています。

| FSQ–Overture高信頼候補のOverture側フラグ | 件数 | 0～5m | 5～10m | 10～20m | 20～30m |
| --- | --- | --- | --- | --- | --- |
| True | 676 | 675 | 1 | 0 | 0 |
| False | 678 | 268 | 205 | 163 | 42 |

両データの一致を独立した2つの情報源による確認とは扱いません。sourceの有無から同一POIとは判定しません。

## 手動確認sample

| Sample | 確認件数 | 生成時のreview_status |
| --- | --- | --- |
| high_confidence | 10 | pending |
| ambiguous | 20 | pending |
| unmatched_nearby | 10 | pending |

固定seed=42。pair別プールから決定的に抽出しました。近接相手がいる対応なしsampleには、
人間が確認するための近傍候補最大3件も格納しました。この表示順はmatchingのtie breakではありません。
2026-09-28、プロジェクトオーナーから上記40件の目視レビュー完了と、現行ルールの採用承認が報告されました。
3pairすべてを含み、オーナー報告による概ねの内訳は以下のとおりです。

| Sample | FSQ–Overture | FSQ–OSM | Overture–OSM |
| --- | --- | --- | --- |
| high confidence | 4 | 2 | 4 |
| ambiguous | 9 | 3 | 8 |
| unmatched nearby | 4 | 2 | 4 |

- high confidenceから抽出した10件を目視確認した範囲では、明らかな誤対応は確認されませんでした。
- ambiguousには、同一POIらしい空白・句読点・支店名・表記揺れの例と、近接する別POIと思われる例の両方が含まれました。自動では断定しないケースを残す設計の妥当性確認です。
- unmatched nearbyには近接する別店舗やOSMの名称欠損等があり、自動対応しない判断に不自然な例は確認されませんでした。
- 約30mを少し超える同名候補や30～100mの名称一致候補も確認し、探索100m・自動採用30mを維持しました。
- 名前正規化、matching rule、一対一制約、閾値、既存実測値は変更していません。

この少数sample確認は統計的なprecision / recall / accuracy評価ではなく、ground truthを構築したものでもありません。
高信頼候補全体の正しさを保証するものではありません。30mは精度を保証する距離ではなく、100mまで競合を監査しつつ自動採用を近距離に限定する実験上の閾値です。

ローカルCSV・manifest・Notebookの生成処理が示す`pending`は自動生成時点の状態です。
今回のオーナーレビュー完了はこの節に記録し、生成物の書き換えや追加sample生成は行っていません。

## 実行時間・保存サイズ

- Foursquare COUNT・取得・検証: 45.282秒。
- Foursquare保存データ: 5,241,128 bytes（Places/Categories JSON、manifestを除く）。
- 最終比較処理・成果物保存: 280.707秒（入力検証・Notebook起動・HTML生成はこの計測外）。
- 最終比較成果物: 59,299,974 bytes（56.55 MiB、manifestを除く）。
- 通信量、スキャン量、ピークメモリは未観測。値を推測していません。比較処理のproviderへの新規問い合わせは0回。

## テストと公開安全性

- `uv sync --locked --group notebooks --group osm`: 成功。新規依存・lockfile変更なし。
- `python -m unittest discover -s tests -v`: 既存3providerを含む64テスト成功。
- COUNT照合、保存後件数、hash改変拒否、500件入力拒否、空名称、距離、競合、一対一、補助情報、three-way、source監査、住所補完を架空データで検証。
- 最終Notebookの7コードセルが全セル実行成功。HTMLを生成し、ブラウザーで表・見出し・注意事項の表示を確認。
- 公開Notebookのoutputs / execution_count / attachmentsは空。raw POIや認証情報は埋め込んでいません。
- 元の3provider取得結果は保存済みhashと一致。Notebook 01～03、AOI、pyproject.toml、uv.lockは変更なし。
- 実データ、実行済みNotebook、HTML、sample、manifestはGit管理外。公開候補の認証情報・絶対パス・サイズとdiffを点検。

## 解釈上の限界

- 対象は今回の取得条件で得たレコードです。地域全体の実店舗数でも営業中店舗数でもありません。
- 取得時点、カテゴリ／タグ、geometry、営業状態の意味が異なります。
- provider内の重複した実体を本格的に名寄せしていません。OSM node/way/relationは型を含むIDで区別します。
- 名前欠損・表記差・位置差により対応を見落とします。OSMには名称なし236件があります。
- 共通ドメイン・代表電話・建物住所に由来する弱い要確認候補が多数あり、要確認ペア数を店舗数と解釈しません。
- hostname差や表記差で保守的に保留する場合があります。閾値は正解データで校正していません。
- オーナーによる40件のsample確認は完了しましたが、高信頼ラベルは正解率や確定的な同一性を保証しません。
- 生データ・対応表は再配布せず、元のライセンス・帰属条件を維持します。
- 過去snapshotが利用不可になった場合や保存済みOSM応答がない環境では、この実行の完全な再現はできないことがあります。

© OpenStreetMap contributors。Foursquare / Overtureの帰属・利用条件は[利用ガイド](poi-comparison.md)を参照してください。
