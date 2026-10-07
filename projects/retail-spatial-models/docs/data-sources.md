# 出典候補と確認状況

確認日：2026-10-07。分析用データは未取得。Issueの2026-10-06調査報告と、このラボでの再確認を区別する。採用・再配布を一括承認する文書ではない。

## NY Lottery：第一候補、条件付き

- 正式名：Lottery Daily Retailer Sales (By Game): Beginning 2024。配布ID `xyvi-fbb9`。
- [公式入口](https://data.ny.gov/d/xyvi-fbb9) / [公式メタデータ](https://data.ny.gov/api/views/xyvi-fbb9.json) / [API](https://data.ny.gov/resource/xyvi-fbb9.json)。提供者はIssueでNew York State Gaming Commission / New York Lotteryと報告されている。
- 今回メタデータを直接読み、名称と`bus_day`、`agtno`、住所、`chain`、`bustype`、ゲーム別売上列を確認した。`numbers_day`はDaily NUMBERS DAY Sales Amount。ゲームは行ではなく列に分かれる。一意キー・実収録期間・金額単位・日次完全性はデータ/仕様書での確認が残る。
- `georeference`の説明は、住所要素から生成された座標で、街路住所がない場合は特定住所を表さない代表点であることを明記している。正確な店舗位置と一律に扱わない。
- メタデータの`licenseId`はnull。これは利用禁止とも自由利用とも判断できない。個別条件と下記規約本文を確認してから取得・利用する。

| 資料 | Issueでの報告 | 今回の確認・残件 |
| --- | --- | --- |
| [Overview](https://data.ny.gov/api/views/xyvi-fbb9/files/195f1129-f96a-40e6-97a6-1a77f60a3f1b?filename=GAMING_LotteryDailyRetailerSalesByGame_Overview.pdf) | 2024-09-01開始、UNAUDITED SALES DATA | Web取得失敗。本文再確認前。監査済み会計・完全な期間とは扱わない |
| [Data Dictionary](https://data.ny.gov/api/views/xyvi-fbb9/files/74f6ec72-b2a8-4f6a-89c0-f379c42752dd?filename=GAMING_LotteryDailyRetailerSalesByGame_DataDictionary.pdf) | 売上列等の定義 | 今回本文未確認。paid/settles等を総売上へ足さない |
| [OPEN-NY Terms](https://data.ny.gov/api/views/77gx-ii52/files/ef0c1840-ad54-4240-92fd-6397c49fde46?filename=OPEN-NY_20Terms_20of_20Use.pdf) | 民間での再利用可、個別条件は別 | Webツールで本文取得不可。現行規約・Attribution・集計/図/抜粋の公開条件は未確定 |
| [RFP追加表](https://gaming.ny.gov/rfp-1052-addendum-1-attachments) | 稼働期間・端末数等への言及 | 表本体・利用条件・結合可能性未確認。必須入力にしない |

2026-10-05の販売記録が存在したという記述はIssue提供情報で、今回の実データ確認結果ではない。最新日付があることはその月の完全性を意味しない。取得開始前に、採用列・範囲・期間・利用条件・取得コマンドを確定する。取得後はUTC、件数、サイズ、SHA-256、クエリとスキーマを保存する。ロゴ等は転載しない。出典・加工内容は記事に表示する。

## 補助データ・代替候補

以下は公式入口を引き継いだ候補で、今回の採用確認はしていない。使用前に個別に版・ライセンス・Attribution・再配布条件を確認する。

| 候補 | 入口 | 用途・注意 |
| --- | --- | --- |
| Census / ACS | [ACS](https://www.census.gov/programs-surveys/acs) | 人口の観測期間、地理粒度、MOE、境界版を確認。公開年と観測年を分ける |
| OSM / Overture | [OSM](https://www.openstreetmap.org/copyright) / [Overture Places](https://docs.overturemaps.org/guides/places/) | 道路・周辺POI。ODbL等は取得物/成果物ごとに確認。confidenceは人気ではない |
| Iowa | [公式](https://data.iowa.gov/catalog/dataset/1263) | Issueによると仕入れデータ。消費者POS売上に置き換えない |
| Texas | [公式](https://data.texas.gov/dataset/Mixed-Beverage-Gross-Receipts/naix-2893) | 酒類等の申告額。一般小売売上ではない。公開条件未確認 |
| Seoul | [公式](https://data.seoul.go.kr/dataList/OA-15572/A/1/datasetView.do) | 商圏・業種単位の推計。個店実測ではない |
| 世田谷人口 | [公式](https://www.city.setagaya.lg.jp/01110/5193.html) | 日本のアクセス評価候補。町丁目内の配置は未観測 |

## モデル資料の精査

- [CDM解説](https://geowieland.github.io/huff_official/competing-destinations.html)：今回本文確認。店舗の集積項をHuffへ追加する構成で、Fotheringham (1985), DOI `10.1068/a170213`を参照している。採用時は原典も確認し、係数の符号から因果効果を断定しない。
- [2SFCA解説](https://geowieland.github.io/huff_official/2sfca.html)：今回本文確認。このページの主式は基本2SFCAであり、そのままHuff型2SFCAと呼ばない。Huff統合の参考としてLuo (2014), DOI `10.1111/tgis.12096`を挙げている。採用式の確認は実装前の残件。
- 両解説ページ末尾はGPL-3.0表記。参考リポジトリのコードをApache-2.0として無条件に移植しない。現段階は参照のみ。数式を理解して小さく独立実装し、コード・文章等を再利用する場合は対象物のライセンス適合性を別に確認する。
- [Hansen解説](https://geowieland.github.io/huff_official/hansen-accessibility.html)は未再確認。[2022年の食品アクセス研究](https://doi.org/10.3390/ijgi11110579)は今回アクセス制限で本文未確認。
- Issueにある2026年の緑地・買物行動・SNS・強化学習の論文群は未再確認。参考候補としてIssueに保持し、現段階の採用根拠・実装仕様には使わない。

この精査では公式メタデータと上記2解説をメモリ上で閲覧した。APIの売上行、原データ、依存、外部コードは保存していない。規約未確認を隠して「ブログ利用可能性確認済み」としない。
