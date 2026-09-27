# 同じ吉祥寺AOIで3つのPOIデータを比較する

[Notebook 04](../notebooks/04_poi_comparison.ipynb) / [実測・検証記録](poi-comparison-validation.md)

Foursquare Open Source Places、Overture Maps Places、OpenStreetMapを同じbboxで並べ、
取得レコード数、属性presence、保守的な同一POI候補を確認します。
正解データを持たないため、網羅率・精度・優劣ランキングは評価しません。

## 準備と実行

リポジトリルートで実行します。Python 3.11+、uv、個人のPlaces Portal tokenが必要です。
tokenはプロジェクトの`.env`にある`FSQ_OS_PLACES_TOKEN`だけを使用し、Notebookへ書きません。

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD 'data/cache/uv'
$env:IPYTHONDIR = Join-Path $PWD 'data/cache/comparison/ipython'
$env:JUPYTER_RUNTIME_DIR = Join-Path $PWD 'data/cache/comparison/jupyter-runtime'
uv sync --locked --group notebooks --group osm
uv run --locked --group notebooks --group osm jupyter lab notebooks/04_poi_comparison.ipynb
```

このリポジトリにはデータを同梱しません。新しいcloneでは先に
[Overture編](overture.md)と[OSM編](openstreetmap.md)の手順で取得・保存してください。
比較処理からOvertureやOverpassを呼び出すことはありません。
OSMの過去応答がない環境では過去の状態を完全再現できず、新しいbase timestampの別実験になります。

Notebookの`prepare_inputs(acquire_foursquare=True)`は、完成済みFoursquare全件取得結果が
なければ、既存provider APIで次の固定snapshotを取得します。結果があれば再利用します。

| Dataset | 固定snapshot / release |
| --- | --- |
| Foursquare Places | `2325979374271449319` |
| Foursquare Categories | `5006175908264532092` |
| Overture Places | `2026-09-23.0` |
| OSM | 使用する保存済みmanifestのbase timestamp |

同一条件の独立したCOUNT、取得行数、unique ID数、保存後の行数の一致を確認してから
比較へ進みます。snapshotが利用できない、取得が失敗する、検証に不一致がある場合は停止します。
Foursquare全件取得の時間予算は300秒、既存接続のDuckDBメモリ上限は1GBです。
SQLからLIMITを除いたことだけでは成功としません。500件の旧サンプルは入力に使えません。

入力はprovider別の最新の保存済みmanifestを選び、hash、AOI、release、COUNT等を検証します。
新しいファイルが不適合でも古いものへ黙って切り替えません。過去実行を再現する場合は
comparison manifestの`inputs`に記録された相対パスを`prepare_inputs(paths={...})`へ渡します。
`paths`のキーは`foursquare`、`overture`、`osm`、値は各取得manifestの相対パスです。

## 対象範囲と意味

[既存AOI](../configs/aoi/kichijoji.toml)のwest=139.574、south=35.699、east=139.586、
north=35.708を再利用します。境界を含みます。

- Foursquare: `country=JP`とbboxを満たす、固定snapshotのレコード全件。
- Overture: 固定releaseから既存処理で取得したPoint POI。
- OSM: 8キーOR条件、既存OSMnx 2.1.1のgeometry化と代表点による最終採用結果。
- 共通の営業状態filterをかけません。NULLは営業中を意味しません。
- OSMの代表点は入口ではなく、AOIと交差する全geometryを含む定義でもありません。

3データのsnapshotは同時刻ではありません。比較実行日時と元データ取得日時を分けて記録します。

## 比較ビューとpresence

`source / source_id / name / name_normalized / longitude / latitude / address_parts /
phones / websites / raw_category / brand / status_raw / has_*`を持つ最小ビューです。
元の名前、複数の電話・Webサイト、構造化住所、provider固有カテゴリを保持します。
canonical categoryは作りません。元データも変更しません。

presenceの分母はproviderの取得全レコードです。欠損行を分母から除外しません。

| 属性 | 「値あり」の意味 |
| --- | --- |
| name | 空白だけでない代表名称 |
| address | 国コード以外の住所成分が1つ以上。市名だけの場合も含む |
| phone / website | 非空の値が1つ以上。有効な番号・URLであることまでは要求しない |
| category | 元のカテゴリID、分類、対象タグの存在 |
| brand | 明示的なbrand情報。Foursquareは取得schemaに列がなくN/A |

presenceは正確性、有効性、完全な住所、最新性の評価ではありません。
OSMは採用済みIDだけに保存済みOverpass応答の`addr:*`を補完します。
構成node等を比較行へ追加せず、新しいOverpass queryも実行しません。

## 候補生成と判定

名前はNFKC、strip、連続空白の統一、lowercaseのみです。語・記号・店舗名の一部を削除しません。
空名称同士は一致扱いしません。元のnameも保存します。

EPSG:4326からEPSG:32654へ投影し、Shapely STRtreeで100m以内の**全空間候補**を列挙します。
距離単独や最近傍1件だけでは判定しません。
名前類似度は`SequenceMatcher(autojunk=False)`の両方向ratioの平均です。
0.90は要確認候補を探す暫定値であり、高信頼への昇格条件ではありません。

高信頼の一致候補は、非空の正規化名完全一致、30m以内、双方で一意、競合なし、明確な補助属性矛盾なし、
をすべて満たす組です。100m以内の他の同名・類似度0.90以上の候補を強い競合として残します。
補助情報だけが一致する組は要確認として保存しますが、共通住所やチェーンのドメインだけで強い競合とはしません。
近い順やID順で競合を解消せず、最大マッチ数を狙う最適化も行いません。

電話は明確な日本番号のみ軽く正規化し、Webサイトはhostnameを比較します。
チェーン共通ドメインや代表電話の可能性があるため、補助一致だけでは高信頼になりません。
比較可能な電話・hostnameの集合が両側にあり共通値がなければ`conflicting`です。
住所は自由記述の完全一致を補助とし、両側に有効な7桁郵便番号があって不一致の場合のみ明確な矛盾とします。
住所表記の違い、市名の一致、比較不能な値を無理に同一／別店舗へ変換しません。

候補表には距離、名称、名称類似度、補助情報の`supporting / conflicting / unavailable / not_comparable`、
分類と理由を保存します。要確認理由は`multiple_exact_name_candidates`、`similar_name_only`、
`distance_over_auto_threshold`、`competing_candidate`、`conflicting_phone`等です。

対応が得られないレコードは次に分けます。

- `no_spatial_candidate`: 候補距離内に相手がいない
- `spatial_candidate_but_no_name_evidence`: 近接相手はあるが対応根拠が足りない
- `ambiguous_candidate_exists`: 要確認候補はあるが採用できない
- `insufficient_evidence`: 名称欠損等で根拠が足りない

これらは「他データに存在しない」という意味ではありません。
分類別レコード数はpairwise・左右別で集計し、候補ペア数と混同しません。

three-wayは3ペアの高信頼の辺がすべてそろう三角形だけです。
2辺の連鎖は統合せず、1組に各providerが1件ずつであることを検証します。

## 距離とsource監査

3ペアで30/50/100mの候補数・競合数を記録します。この感度分析では自動採用距離30mを固定し、
探索距離だけを変えます。正規化名完全一致の距離分布は、非空の名前で先に候補を絞ってAOI全体で計算し、
100m超も記録します。100m超の組をマッチングへ追加するものではありません。

Overtureの`sources.provider`または`sources.dataset`がFoursquareであることを
`has_foursquare_source`へ記録します。これは候補生成や判定には渡さず、一致後の監査にのみ使います。
FoursquareとOvertureの一致は、独立した2つの情報源による確認とは限りません。

## 保存・手動確認・テスト

Foursquare全件取得は`data/raw/foursquare_full/`、比較生成物は`data/raw/comparison/`へ保存します。
入力hash、取得条件、snapshot、時刻、規則、依存バージョン、コードhashをmanifestに記録します。
通信量・スキャン量・ピークメモリは測定していなければnullです。

手動確認CSVは固定seed=42で、pair別の候補プールから高信頼最大10件、要確認最大20件、
近接相手がいる対応なし最大10件を抽出します。全候補からの一様標本や精度推定用標本ではありません。
`review_status=pending`で保存し、人間による確認前に確認済みと扱いません。
今回の40件はプロジェクトオーナーが目視確認し、現行ルールの採用を承認しましたが、ground truthによる精度評価ではありません。
確認結果と生成時のpending表記の扱いは[検証記録](poi-comparison-validation.md#手動確認sample)を参照してください。

```powershell
uv run --locked --group notebooks --group osm python -m unittest discover -s tests -v
```

公開Notebookは出力・execution count・attachmentsを除去します。
実行済みNotebook、HTML、候補表、CSV、元データはGit管理外です。

## 利用条件

コード・オリジナル文書はApache-2.0ですが、外部データを一括で再許諾しません。
2026-09-27の設計調査で確認した公式資料と既存の各providerガイドを引き継ぎます。

- Foursquare: [Apache-2.0とNOTICE](https://opensource.foursquare.com/places-notice-txt/)。帰属・変更表示等の条件を維持。
- Overture: [source別の条件](https://docs.overturemaps.org/attribution/)。Foursquare由来、CDLA、CC0等を区別。
- OSM: [ODbL 1.0](https://www.openstreetmap.org/copyright)。© OpenStreetMap contributors。帰属とライセンスを明示。

記事にはデータ提供元・取得条件と集計を示します。生データや対応表は公開しません。
今後データベースや抽出データを配布する場合は、ODbLの派生データベース等の条件を含め、
配布物に応じた条件を再確認します。集計・地図であっても元データの条件を無視できるとは扱いません。
