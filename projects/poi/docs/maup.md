# 固定外枠でMAUPを確かめる

仮タイトル：**地図の区切りで答えが変わる？　PythonでMAUPを確かめてみた**

[Notebook 10](../notebooks/10_maup.ipynb) / [実測と記事引き継ぎ](maup-article-handoff.md)

## 事前に固定する条件

吉祥寺の既存N02-25代表点、EPSG:6677の東西南北2,000m、4km四方（16km²）。南西を原点とし、北を上とする。
250m正方形256区画、500m正方形64区画、1km正方形16区画をスケール比較。
500m正方形、東西1,000m×南北250m、東西250m×南北1,000mは各64区画・各0.25km²としてゾーニング比較。
重複・隙間・部分区画なし。内部境界は東・北へ、外周北東端は最後の区画へ割当。丸め誤差は格子線から1e-8m以内だけ吸収。

入力は保存済み20261015T080101Z-tokyoのOverture 2026-09-23.0。取得外接矩形が固定外枠を覆うことをメタデータで検査し、SHA-256を照合。観測点の存在範囲で取得済みと判断しない。
会社資産、新しい取得、Notebook 09の再計算・変更は行わない。

カテゴリはconfigs/region_features.tomlのbasic_categoryによる既存6群。食事＝restaurant/casual_eatery、カフェ＝cafe/coffee_shop、バー＝bar、衣料＝fashion_and_apparel_store、美容等＝personal_or_beauty_service、食品小売＝food_and_beverage_store。
1POIを1群へ割当。alternateカテゴリを多重計上しない。未定義の非欠損カテゴリはその他、null/空文字は欠損。分母は区画内全POI。0件区画は件数・密度0、構成比は未定義NaN。未取得を0扱いしない。
営業状態による除外なし。POI登録数は営業中店舗数・実店舗数ではない。

## 比較方法

全区画を等重みとし、件数・密度・8群の件数/構成比について平均・中央値・P90・最大を出す。P90は線形補間。NaNは構成比分布から除外し有効数・未定義数も報告。
6群の件数について全15組×5方式＝75のSpearmanを保存。ゼロ件区画も相関の対象。同値順位は平均順位、定数列の相関は未定義。p値で有意差を判定しない。
代表例は結果を見る前に食事×カフェと固定。全組の差は500m正方形を基準として保存し、最大変化だけで結論を作らない。
スケール変更で区画数・標本数も変わる。相関の変化を因果関係や個々の店舗の関係へ読み替えない。

## MAUPとNotebook 09の区別

[Esriの定義](https://support.esri.com/en-us/gis-dictionary/modifiable-areal-unit-problem)に沿い、集計単位の大きさによる違いをスケール効果、同じスケールで区切り方による違いをゾーニング効果として調べる。
今回の外枠・点集合は固定で、全域を分割する。Notebook 09は駅中心AOIの広さと入力集合が変わり、駅間AOIも重複するため、教科書的な固定地域の分割MAUPと完全に同じではない。
地域メッシュ制度、円、徒歩圏、ボロノイは扱わない。吉祥寺4km四方以外への一般化、需要・売上・優劣の推定は行わない。

## 再実行と公開条件

POIテーマの既存uv環境で実行する。OS Pythonへの追加インストール・新依存は不要。

```powershell
uv run --no-sync python -m geoai_open_lab.maup
uv run --no-sync python scripts/execute_maup_notebook.py
node scripts/render_maup.cjs
uv run --no-sync python -m unittest discover -s tests -q
```

保存済み入力がないcloneでは実行できない。自動ダウンロードはしない。
出力はテーマ内data/cache/maup/kichijoji-v1（Git管理外）。cells.csv、distribution.csv、correlations.csv、operating_status.csv、manifest.json、SVG/PNG、実行済みNotebook/HTMLを保存。
出典・条件は[既存出典資料](region-feature-sources.md)と[データポリシー](../../../docs/data-policy.md)を継承。source/licenseは元Parquetに保持し、Foursquare NOTICE全文とApache LICENSEを生成物へ同梱。今回加工日は2026-10-22。
Git公開はコード、テスト、出力なしNotebook、文書。生データ・生成物は公開リポジトリへ追加しない。
