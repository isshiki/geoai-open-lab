# 実験05：駅アクセスと高齢化率の取得準備

確認日：2026-10-04。状態：**3ZIP・道路本体・限定参照補完の取得と監査を実施。歩行属性の監査と[グラフ構築仕様](station-access-aging-walking.md)を整理。徒歩グラフ・高齢化率・距離・相関の分析は未実施**。
実測値は[入力検証記録](station-access-aging-validation.md)を参照。以下の取得前見積りは承認時点の記録です。
[計画書第3案](station-access-aging-plan.md) のP0と感度確認一覧を維持します。
この文書は、取得を承認するための対象・範囲・予算と、採用候補ごとの利用条件を記録します。
[データポリシー](data-policy.md) に従い、原データをGitへ保存しません。

## 1. 取得を二段階に分ける

初回は下記の人口・駅・市域の3配布物だけを取得し、ローカルでメタデータ、列、geometry、対象域を監査します。
相関の計算・高齢化率と距離の突合はまだ行いません。道路・駅入口は初回取得に含めません。

| 用途 | 採用候補・対象配布物 | 基準日・版 | 取得前の容量確認 |
| --- | --- | --- | --- |
| 人口 | e-Stat T001142、JGD2011・250m、人口及び世帯、第1次地域区画5339 | 調査日2020-10-01、配布一覧の公開（更新）日2024-03-14 | HEADは200。`tblT001142Q5339.zip`、Content-Lengthなし。容量未確認 |
| 駅 | 国土数値情報N02、全国 `N02-20_GML.zip` | 2020-12-31、製品仕様書2.3 | 一覧8.04MB、HEAD 8,436,695 bytes |
| 市域 | 国土数値情報N03、東京都 `N03-20200101_13_GML.zip` | 2020-01-01、製品仕様書2.4 | 一覧11.67MB、HEAD 12,233,048 bytes |

容量は配布一覧の表記とHTTPヘッダーを分けて記録しています。取得済み容量ではありません。
N02のLast-Modifiedは2021-12-13、N03は2020-06-29（いずれもUTCのHTTPヘッダー）であり、データの基準日とは異なります。
人口のHEADにはLast-Modifiedもありません。公開日は内容の不変性を保証しないため、取得UTCとSHA-256を別途保存します。

### 初回取得の実行予算案

- 対象は上表の3ZIP。駅と市域の合計は20,669,743 bytes（約20.67MB）。人口を含む総量の実測値は未確認。
- 容量推測の代わりに、1ZIPあたり32MiB、3ZIP合計64MiB、展開後合計512MiBを停止上限にする。
- 直列取得。1ファイル5分、取得工程全体15分を上限とする。これは所要時間の予測ではなく実行予算。
- 成功済みファイルはSHA-256を検証して再利用する。失敗時の自動再ダウンロードはせず、理由を報告する。
- ZIP展開前にパストラバーサル、展開サイズ、重複パスを確認する。想定外のHTML・認証要求・配布変更は停止する。
- 保存先は `data/raw/station_access_aging/`、監査・manifestは `data/cache/station_access_aging/`。いずれもGit管理外。
- 有料API・クラウド資源を作らない。通常の公開ファイル配布を利用し、APIキーは用意しない。実際のGETによる取得成功は未確認。

この初回取得の確認後、3配布物だけを取得・監査します。追加地域・再取得・道路取得は別途提示します。

## 2. 人口：e-Stat T001142

提供者は総務省統計局、配布は政府統計の総合窓口e-Statです。

- [配布一覧：T001142・5339](https://www.e-stat.go.jp/gis/statmap-search?page=1&type=1&toukeiCode=00200521&toukeiYear=2020&aggregateUnit=Q&serveyId=Q002005112020&statsId=T001142&datum=2011&meshCode=5339)
- [CSV配布リンク（ZIP応答）](https://www.e-stat.go.jp/gis/statmap-search/data?statsId=T001142&code=5339&downloadType=2)
- [T001142定義書](https://www.e-stat.go.jp/help/data-definition-information/downloaddata/T001142.pdf)
- [e-Stat利用規約](https://www.e-stat.go.jp/terms-of-use) / [統計GIS機能利用規約](https://www.e-stat.go.jp/gis-terms)

規約は政府標準利用規約第2.0版準拠（2016-01-29制定）、CC BY 4.0互換の記載を確認しました。
統計GISのコンテンツ利用はe-Stat利用規約に準じます。出典と加工表示、第三者権利・個別条件に従います。
表・集計の掲載時は「総務省統計局『令和2年国勢調査に関する地域メッシュ統計』（e-Stat）を加工して作成」と配布URLを記載します。
この数値統計の取得・ローカル監査を初回用途とし、原データの再配布はしません。独自コードのApache-2.0をデータに適用しません。

都道府県単位の追加提供日2025-10-09と、今回使う第1次地域区画単位の更新日2024-03-14を混同しません。
5339の配布を選び、取得後に2市域を覆うことと対象メッシュの欠落を検査します。市境で人口を面積按分しません。

定義書で重ならない年齢3区分、世帯数、秘匿処理を確認済みです。列コードと項目名を照合し、PDF抽出で隣接する階層番号を列コードに連結しません。
「総人口は年齢不詳を含む」という注記はありますが、**採用配布物の不詳補完の有無は明示根拠を確認できていません**。
不詳の残存や列の差だけから補完方式を断定しません。確認できるまでは市の公表高齢化率との比較・人口率の解釈を保留します。
取得後の監査では秘匿・合算を先に判定し、合算先の年齢内訳と単独メッシュ総人口を比較して「不詳人口」としません。

## 3. 駅：N02 2020年版

提供者は国土交通省。全国ZIPを取得し、Stationレイヤーから分析対象2市＋5kmに関係する駅を抽出する案です。
全国の鉄道路線を分析対象にする意味ではありません。

- [配布案内・属性・2020年利用条件](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N02-v2_3.html)
- [配布ZIP](https://nlftp.mlit.go.jp/ksj/gml/data/N02/N02-20/N02-20_GML.zip)
- [鉄道区分コード](https://nlftp.mlit.go.jp/ksj/gml/codelist/RailwayClassCd.html) / [事業者種別コード](https://nlftp.mlit.go.jp/ksj/gml/codelist/InstitutionTypeCd.html)
- [国土数値情報利用規約](https://nlftp.mlit.go.jp/ksj/other/agreement.html)

2020年はオープンデータとの個別表示を確認しました。現行規約はPDL1.0（2026-03-23施行）、個別例外優先です。
出典案は「国土交通省『国土数値情報（鉄道データ、2020年）』を加工して作成」＋配布案内URL。
取得・加工・掲載は適用規約と個別条件に従い、元データ・駅一覧の再配布は今回行いません。

N02_001は11、12、14、15、16、21、22、23、24を採用候補、13（鋼索）、17（無軌条）、25（浮上式）は初回除外案とします。
N02_002は2～5（JR在来線、公営、民営、第三セクター）を対象、1（新幹線）は除外案です。出現コードと除外数を監査します。
2020年版の公開属性一覧はN02_001～005であり、駅グループコードを前提にできません。
A11用のグループ確定は公開根拠と実ファイルで別途行い、同名だけで自動統合しません。未確定ならA11を未実施と記録します。
主仕様の路線別中点は維持します。不正・非連続geometryは黙って補修せず別ステータスにし、数と理由を報告します。

## 4. 市域：N03 東京都2020年版

- [現行配布案内（過年度ファイルも掲載）](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-v3_1.html)
- [2020年の製品仕様案内](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-v2_4.html)
- [東京都ZIP](https://nlftp.mlit.go.jp/ksj/gml/data/N03/N03-2020/N03-20200101_13_GML.zip)
- [現行規約](https://nlftp.mlit.go.jp/ksj/other/agreement.html) / [旧約款準拠規約](https://nlftp.mlit.go.jp/ksj/other/agreement_02.html)
- [国土地理院：測量成果の利用手続](https://www.gsi.go.jp/LAW/2930-index.html)

現行案内は2018年以降をオープンデータと記載する一方、旧2.4案内は2018年度以外を「商用可」と記載しており、表記に差があります。
現行案内からはPDL1.0適用と読めますが、旧版の条件をなかったことにはしません。
旧約款でも出典・加工者表示等により商用利用可能とされるため、今回の**取得とローカル監査**は両方の条件を踏まえて進める案です。
旧約款の条件・適用限界の伝達も保持し、データを無条件に再許諾できるとはしません。
原典は国土地理院の数値地図で、複製・二次利用には測量成果の手続が関係します。内部利用と外部への図版・データ提供を分け、
外部公開の具体的形態について申請要否を確認するまで境界図や派生境界データは公開しません。
出典案は「国土交通省『国土数値情報（行政区域データ、2020年）』を加工して作成」＋配布案内URL。必要な原典表示も保持します。

N03_007の13203（武蔵野市）・13204（三鷹市）を名前と照合して選択し、EPSG:6677上で市域を統合します。
2020-01-01市域と2020-10-01人口の時点差は残るため、境界変更の有無を別途確認します。
道路取得範囲はこの市域の5,000m bufferを覆うbboxとし、数値は実ファイルの監査後に固定します。
取得bboxを分析AOIと同一視しません。人口の採用条件は計画書どおり中心点による市域判定です。

## 5. 道路：Overture Transportationは第2段階

新規実験の候補releaseは **2026-09-23.1、schema v2.0.0**。既存Places実験の固定版は変更しません。
[公式リリースノート](https://docs.overturemaps.org/blog/2026/09/23/release-notes/) は.1修正版を案内しています。
TransportationのOSM cut-offは2026-09-09であり、2020年道路網ではありません。

- [Transportationガイド](https://docs.overturemaps.org/guides/transportation/)
- [通行モード・条件付き規則](https://docs.overturemaps.org/guides/transportation/scoping-and-travel-modes/)
- [帰属・ライセンス](https://docs.overturemaps.org/attribution/) / [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/)
- [配布版の保持期間](https://docs.overturemaps.org/release-calendar/)

TransportationはODbL。公式帰属一覧のOSM contributorsとTomTom、採用レコードのsourcesを記録します。
図・集計・派生DBごとの公開判断は計画書§3を適用し、Apache-2.0で再許諾しません。
固定releaseの公開保持は最大60日との案内があるため、版固定だけで永続的な再取得を保証しません。
許可を受けて取得した範囲はローカル保存し、版・取得日・ハッシュ・クエリを残します。

対象は `theme=transportation/type=segment` の `subtype=road` と必要なconnector情報。
通行条件と接続位置の監査に必要な列を保持し、bboxによる抽出前に世界全体をローカル取得しません。
保存量・転送量・スキャン量は未測定で、bboxが小さいだけで通信量が小さいとは判断しません。
第1段階で範囲を固定した後、公開メタデータによる見積りと実行上限を提示し、道路取得を別途確認します。

Overtureが完成済みの徒歩所要時間を返すわけではありません。歩行可能なネットワークを構築して最短距離を計算する必要があります。
規則がない場合の通行可否はアプリ側の判断が必要で、欠測を一律「徒歩可」にしません。
距離を分数に換算する場合も歩行速度の仮定による値です。初回はm/kmで報告します。
徒歩属性、条件付き制限、connector接続の品質が不足すれば、その理由を報告してOSM代替を検討します。

## 6. 取得後に確認する順番

1. 承認された3ZIPの取得UTC、実容量、SHA-256、取得URL、環境とコード版をmanifestへ記録。
2. 配布物のメタデータと利用条件、人口の列・秘匿、N02/N03のCRS・geometry・コードを監査。
3. 人口の補完方式、境界の時点差、駅コード・グループの未確定事項を解消する。未解決の分析は保留。
4. 市域＋5kmと駅候補を確定し、道路取得の範囲・列・実行予算を提示。
5. 道路取得の確認後に、経路処理と架空データのテストを実装。測定品質の成立後にP0・感度確認を実行。

## 7. 入力取得・監査の再現

既存の依存グループを使用します。新規依存は追加していません。

```bash
uv sync --locked --group osm --group notebooks
# 新規取得には対象・予算の承認が必要。初回承認済みの3ZIPだけを取得する場合：
uv run --no-sync python scripts/station_access_aging_acquire.py --download
# 保存済みZIPのオフライン整合性検査（ダウンロードしない）：
uv run --no-sync python scripts/station_access_aging_acquire.py
uv run --no-sync python scripts/station_access_aging_audit.py
uv run --no-sync python -m unittest discover -s tests
```

取得処理は成功済みZIPの上書き・自動再取得を行いません。manifestのハッシュが一致しない場合は停止します。
ZIPは展開せず読み取り、人口テキストとShapefile属性はCP932を明示します。
監査は項目コードと日本語ラベルを照合し、非重複年齢区分、秘匿区分・参照先、メッシュ中心、市域、駅線形を検査します。
`data/cache/station_access_aging/` にmanifest、入力監査JSON、行単位の監査CSV、駅候補Parquetを保存します。
これらは原データとともにGit管理外です。公開するのはコード・手順・集約した検証記録だけです。
未掲載メッシュをゼロ補完せず、合算先の年齢合計から単独メッシュの年齢不詳人口を計算しません。
取得後の未確認事項と次の段階への条件は[検証記録](station-access-aging-validation.md)に残します。

## 8. 道路ファイル一覧の事前確認

[公式DuckDB取得案内](https://docs.overturemaps.org/getting-data/duckdb/)の公開S3 bucketを使い、[ListObjectsV2](https://docs.aws.amazon.com/AmazonS3/latest/API/API_ListObjectsV2.html)で固定releaseのsegment・connector一覧だけを取得します。第5節の利用条件を適用し、一覧と監査記録もGit管理外に保存します。

```bash
# 対象・上限を表示（通信しない）
uv run --no-sync python scripts/station_access_aging_road_inventory.py
# 一覧取得。既存保存先がある場合は再取得せず停止する
uv run --no-sync python scripts/station_access_aging_road_inventory.py --fetch
```

受信本文8MiB・最大20要求・120秒を予算とし、各通信の待ち時間は最大10秒です。期限を各要求・読み取りの前後で判定するため、進行中の通信はtimeoutまで継続し得ます。HTTPヘッダー・TLSの通信量は計測対象外。認証情報は使わず、リダイレクト・ページング不整合・予算超過では停止して、完了フラグfalseの記録を残します。

一覧の[実測結果](station-access-aging-validation.md)から、地域限定の取得量はまだ判断できません。次段階の提案は160ファイルの末尾8bytesとfooterのRange GETのみ、本文合計64MiB・最大320要求・全体5分・footer単体8MiBを上限とします。これは推定使用量ではなく停止上限です。Rangeが無視された200応答は本文を読まず停止し、footer長が上限を超える場合も本体取得へ切り替えません。上限付きfooter検査を承認後に実行しましたが、33/160ファイルで部分停止しました。[検証記録](station-access-aging-validation.md)を参照してください。自動再取得は行いません。全体期限は要求・読み取り前後で判定し、進行中通信は最大10秒のtimeoutまで継続し得ます。


```bash
# footer検査の計画表示（通信しない）
uv run --no-sync python scripts/station_access_aging_road_footers.py
# 上記の対象・予算で実行承認を得た後だけ実行
uv run --no-sync python scripts/station_access_aging_road_footers.py --fetch
```

一覧に記録したETagをIf-Matchで照合し、変更済みオブジェクトの混入を拒否します。取得したfooterと報告JSONはGit管理外の `data/cache/station_access_aging/road-footers/` に保存。部分完了も完了扱いにせず、保存先が存在する場合は再問い合わせを拒否します。bbox統計の欠落・null・非有限値は、その列から除外を断定する根拠にしません。row groupが候補から外れるのは有効な統計でbbox非交差を証明できた場合だけです。


## 9. 保存済みfooterからの再開（実行済み・全件完了）

初回reportと33個のfooterは変更せず保持します。再開前に、一覧のSHA-256・release・AOI・オブジェクト順・保存済みfooterのSHA-256・magic・長さ・row group数を照合します。欠損、未記録ファイル、破損があれば取得に進まず停止します。

```bash
# オフライン照合と予算表示。通信しない
uv run --no-sync python scripts/station_access_aging_road_resume.py
# 追加予算の実行承認後のみ
uv run --no-sync python scripts/station_access_aging_road_resume.py --fetch
```

再開対象は未検査127ファイル（segment95、connector32）の末尾8bytesとfooterのみ。追加受信本文512MiB、最大254要求、600秒、footer単体8MiBを停止上限とする案です。前回と合わせた受信本文上限は約575.49MiB。HTTP/TLSヘッダー等は含みません。確認済みsegment footerは約2MBですが、未検査connectorのfooter量は未確認で、512MiBを推定必要量や完了保証としません。

前回33件へのHTTP要求は行いません。34件目のtrailerは前回保存していないため再取得が必要です。新規分と統合reportはGit管理外の `data/cache/station_access_aging/road-footers-resume-01/` に保存し、元reportへ上書きしません。新規分は一覧のETagをIf-Matchで検証します。全体期限は要求・読み取り前後で検査し、進行中通信は最大10秒のtimeoutまで継続し得ます。上限到達で部分停止し、上限拡大や道路本体取得へ自動移行しません。


上記再開は承認後に実行済みです。追加205,406,114 bytes・254要求・220.746秒で全160件を確認しました。[全件結果](station-access-aging-validation.md)の候補row group容量を使い、次は道路本体取得の必要列・connector参照範囲・予算を設計します。保存済み結果を再利用し、同じコマンドで再取得しません。過去の部分停止と再開前の確認記録は履歴として残しています。


## 10. 道路本体の取得計画（2026-10-04、承認後に実行済み）

`python scripts/station_access_aging_road_plan.py` は保存済み全160 footerのハッシュと候補選択を再検証し、通信なしで列単位のRange GET計画を生成します。計画JSONは `data/cache/station_access_aging/road-body-plan.json` に保存します。固定releaseと市域5km bufferを覆うbboxは変更しません。

### 取得列

segment：`id`, `version`, `sources`, `geometry`, `bbox`, `subtype`, `class`, `subclass`, `subclass_rules`, `connectors`, `road_surface`, `road_flags`, `level_rules`, `access_restrictions`, `prohibited_transitions`。
connector：`id`, `version`, `sources`, `geometry`, `bbox`。

実ファイルのスキーマで上記列を確認しました。geometry、接続ID・位置、通行条件・方向・時間・区間指定、施工等のflag、出典・版を保持します。names、速度制限、経路案内等は今回の取得から外します。歩行可否判定は後続の属性監査で行い、制限欠落を無条件の徒歩可としません。

### 受信計画と実行予算案

| 種別 | ファイル | row group | 選択列圧縮bytes | Range要求数 | Range本文bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| segment | 2 | 28 | 86,391,734 | 107 | 86,695,023 |
| connector | 1 | 10 | 24,442,461 | 6 | 24,461,248 |
| 合計 | 3 | 38 | 110,834,195 | 113 | 111,156,271 |

dictionary/data page offsetとcompressed sizeから開始・終了byteを計算し、4KiB以内の隙間を挟む要求を統合します。余分に読む322,076 bytesは上表に含まれます。全オブジェクトを落とさず、選択列のcolumn chunkを読みます。row group内には地域外やroad以外も含まれ、上記行数・容量は地域全体の道路件数・正規化後容量ではありません。

提案上限は受信本文160MiB・最大120要求・600秒。予定113要求・111,156,271 bytesを超えて追加範囲を自動取得しません。HTTPヘッダー等は受信本文と別で未計測。初回メタデータ取得分はこの新規予算に含めません。保存済みfooterを再利用し、If-Match / 206 / Content-Rangeで同一オブジェクトと範囲を検証。読み取り失敗・期限超過・予算超過は部分停止し、無制限のリトライや通常の全体GETへ切り替えません。通信待ちは最大10秒で、期限経過直後の進行中通信はtimeoutまで継続し得ます。

取得・正規化生成物の追加保存上限は512MiBを案とし、raw範囲データ・正規化結果をプロジェクト内Git管理外に置きます。既存の約272MBのfooter保存分は別です。部分ダウンロードはハッシュ付きで保存し、成功済み範囲を再取得しない再開方法を取ります。実行処理と架空データによる復号・上限テストを実装してから、本体へアクセスします。

### connectorの参照整合性と境界

[公式の接続仕様](https://docs.overturemaps.org/guides/transportation/segments-and-connectors/)に従い、共有connector IDを接続の根拠とします。geometryの交差だけで辺を接続しません。`connectors.at` の線上位置と、connector座標との整合も監査対象です。

1. segmentの候補row groupをローカルで復号し、`subtype == 'road'` かつgeometryが取得bboxに交差するものを選択。道路線形は途中で切断せず全体を保持する。欠損・不正geometryは別集計し、黙って修復しない。
2. connector候補の全行から参照IDを照合する。bbox外でも、取得済み候補中に道路の参照先があれば保持する。候補を先にbboxで絞って参照先を落とさない。
3. 参照IDの重複・未解決、座標不一致、bbox外参照数を記録。未解決IDがある場合はそのまま完全なグラフとせず、保存済みメタデータから追加候補と予算を別途提示する。
4. prohibited_transitionsが参照するsegment/connectorも監査し、取得域外の遷移を単に消して通行可能と解釈しない。初回取得だけで全参照が完結する保証はない。

今回は取得・属性/接続性の監査までを次段階とし、経路距離・高齢化率・相関はまだ計算しません。ODbLと出典条件は第5節・計画書§3のままで、生データや派生DBをGitへ追加しません。


### 本体取得・オフライン監査コマンド

```bash
# 上記の取得計画・予算を承認した後だけ実行
uv run --no-sync python scripts/station_access_aging_road_body.py --fetch
# 保存済み範囲から再処理。ネットワークを使用しない
uv run --no-sync python scripts/station_access_aging_road_body.py
```

各Range応答をGit管理外 `data/cache/station_access_aging/road-body/` に保存し、manifestへ範囲・サイズ・SHA-256を記録します。同じ計画で再開する場合は成功済み範囲を照合して再利用し、要求数・受信量・経過時間の予算を引き継ぎます。計画変更や破損・未記録の保存ファイルは停止条件です。ネットワーク再開には都度確認が必要です。

復号はローカルにある範囲と保存済みfooterだけで行い、キャッシュの穴をゼロ埋めしたり追加取得したりしません。取得していない範囲を読む要求はエラーになります。正規化結果は `segments.parquet` と `connectors.parquet`、集約監査は `audit.json` です。外部へデータを再配布しません。

接続監査はID参照、重複、geometry、atの範囲、connector点からsegment線への距離を確認します。EPSG:6677上の1mは監査上の許容差で、通行可能性の保証ではありません。atと線上座標の一致、時間・方向・利用者条件の評価、歩行グラフ構築は別段階です。監査に成功しても「徒歩経路が検証済み」とは呼びません。


上記本体取得は承認後、計画どおり113要求・111,156,271 bytesで完了しました。[実データ検証結果](station-access-aging-validation.md)には未解決connector 6件・通行禁止遷移の未解決segment 1件が残っています。取得成功と歩行グラフの完成を区別し、不足参照・通行条件を解決するまで経路計算へ進みません。


## 11. 不足参照の調査と限定的な補完案

```bash
# 保存済みデータ・footerだけで原因と追加候補を調べる
uv run --no-sync python scripts/station_access_aging_road_references.py
```

2026-10-04の調査で、不足segment 1件は取得済み候補内にあり、bboxによる正規化条件で外れていたと確認しました。参照解決用の補助テーブルへ保存すれば通信不要です。分析AOIや主仕様を広げる根拠にはしません。

不足connector 6件の追加候補は1ファイル・2 row groupです。必要列は既定のid/version/sources/geometry/bbox。メタデータから計算した本文は6,378,447 bytes・2要求です。実行案は**追加受信本文16MiB・2要求・120秒、追加保存32MiB**を停止上限とします。保存済みfooterと取得一覧ETagを再利用し、If-Match/206/Content-Rangeを照合します。既存データは再取得しません。

不足IDと通行禁止遷移の参照IDだけを追加候補から照合し、補助レコードとして分離保存します。6 IDが見つからなくても自動的に範囲を広げません。参照元道路の全geometry bboxを検索に用いていますが、元データの位置不整合を否定できないので完了保証とはしません。取得実行は追加対象・予算の確認後とし、原因調査の承認だけで新規ダウンロードへ進みません。


### 補完の実行結果とオフライン再処理

承認後に2範囲・6,378,447 bytesの補完を実行し、元の不足connector 6件と遷移参照segment 1件を解決しました。補助segment自身の未取得connector 2件は別途残ります。[検証記録](station-access-aging-validation.md)を参照してください。

```bash
# 保存済み範囲から再照合。通信しない
uv run --no-sync python scripts/station_access_aging_road_supplement.py
```

追加取得は同スクリプトの `--fetch` で実行しました。保存先が既に存在するため同オプションでの再取得は拒否します。追加connectorと補助segmentは元結果と分離保存し、元データの前後ハッシュを検査します。補助segmentを歩行グラフへ加えるか、境界外遷移の文脈としてのみ使うかは通行・境界規則の設計時に明記し、参照が見つかっただけで歩行可能と解釈しません。
