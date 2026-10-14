# 記事引き継ぎ：街の数値プロフィール

仮タイトル：**POIデータから地域特徴量を作る：街を数値で表してみる**

主成果は吉祥寺駅周辺1km四方の1行15列。記事の執筆・投稿は未実施。格子密度だけの記事にせず、プロフィールを最初に示す。

## 掲載する実測値

| 地域 | 面積km² | 登録数 | 密度 件/km² | 食事% | カフェ% | バー% | 衣料% | 美容等% | 食品小売% | その他% | 欠損% | 最大密度 | 集中度 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 吉祥寺駅周辺1km四方 | 1.0 | 3591 | 3591.00 | 25.7867 | 5.5416 | 7.2403 | 6.6834 | 8.9390 | 1.7265 | 42.5787 | 1.5038 | 13440 | 3.742690 |

食事等の定義は[列定義](region-feature-columns.md)と[設定](../configs/region_features.toml)が正本。地域ID `kichijoji-station-1km-v1`。構成比の分母には欠損を含む。面積1km²なので登録数と密度は同じ数値だが意味・単位は異なる。類似度へ両方入れない。

## 構成

1. 地域特徴量とは何か（1地域1行、特徴量が列）
2. 吉祥寺駅周辺1km四方を1行にする（公式駅代表点、同一面積）
3. 各数値の意味（密度・構成比・集中度と監査情報）
4. 250m格子16区画から密度と集中度を求める（算出根拠）
5. 欠損・営業状態・データ範囲の限界
6. 次回、23区と多摩を含む東京都内の駅を同じ条件で比較する

## 図と根拠

すべてテーマ内 `data/cache/region_features/kichijoji-1km-v2/` に保存。生データ・生成物はGit管理外。

| 優先 | ファイル | キャプション案 |
| --- | --- | --- |
| 主図 | region_profile.svg | 吉祥寺駅周辺1km四方を数値プロフィールにする。構成比は欠損を含む全POI登録数が分母。営業中店舗数ではない。 |
| 主表 | region_features.csv | 1地域1行、固定15列。密度・構成比・集中度は比較候補であり、採用列と正規化は次段階で決める。 |
| 算出根拠 | density_250_500.svg | 赤点は国土数値情報から算出した駅代表点。北を上に250m16区画・500m4区画。色は密度、数字は登録件数。 |
| 閲覧 | 05_region_features.html | プロフィール表→図→格子の根拠→限界の順で確認する。 |
| 監査 | manifest.json、cells_250.csv、cells_500.csv | 入力版・取得日・コード・設定と数値を照合する。 |

図と記事にはOverture、release2026-09-23.0、取得日2026-10-14、N02-25の出典・CC BY 4.0・加工日、集計者masahiko.infoを残す。Foursquare由来のApache-2.0・NOTICE・変更表示を省略しない。図と同じフォルダのFoursquare-NOTICE.txtとApache-LICENSE.txtを引き継ぎ、[公式帰属情報](https://docs.overturemaps.org/attribution/)と[出典説明](region-feature-sources.md)へリンクする。

## 最小コードと再現

```python
from geoai_open_lab.region_features import run_experiment
from geoai_open_lab.region_figures import save_figures
results, manifest, output_dir = run_experiment()
figures = save_figures(results, output_dir)
```

Notebookは保存済み固定入力だけを使う。初回準備・再現コマンドは[手順](region-features.md#再実行)。新規cloneにはデータがなく、同releaseの公開保持も最大60日であるため再取得を保証しない。

## 注意

今回は1駅の例であり、東京都全駅の比較・類似度・クラスタリング・Embeddingは未実施。範囲は駅中心1km四方で商圏や駅の縄張りではない。営業状態欠損3,590件、カテゴリ欠損54件。その他の大きさは今後全駅で確認し、必要なら群定義を全駅一括で更新する。旧矩形版の値や図を今回の記事へ混在させない。

公開リンク：[Notebook](https://github.com/isshiki/geoai-open-lab/blob/main/projects/poi/notebooks/05_region_features.ipynb) / [手順](https://github.com/isshiki/geoai-open-lab/blob/main/projects/poi/docs/region-features.md) / [検証](https://github.com/isshiki/geoai-open-lab/blob/main/projects/poi/docs/region-features-validation.md) / [東京都全駅の将来計画](tokyo-station-features-plan.md)。
