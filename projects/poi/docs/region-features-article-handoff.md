# 記事引き継ぎ：地域特徴量

仮タイトル：**POIデータから地域特徴量を作る：街を数値で表してみる**

実装と固定入力による実行は完了。記事の執筆・ブログ投稿は未実施。Notebook番号05はPOIテーマ内の実行順で、記事番号ではない。

## 読者に伝える発見

主役は「吉祥寺駅周辺の実験用矩形」を1行にした数値プロフィール。CSVは1行15列で、複数地域へ同じ列を追加する土台になる。

- 面積1.084257km²、登録数3,666件、平均登録密度3,381.118件/km²。
- 食事25.56%、カフェ5.51%、バー7.20%、衣料6.63%、美容等8.81%、食品小売1.75%、その他43.04%、カテゴリ欠損1.50%。丸め前の合計は100%。
- 250m格子の最大密度11,312件/km²、地域平均の3.3456倍。これを集中度の候補とする。
- 営業状態欠損3,665件。登録数は営業中店舗数ではない。

[列定義](region-feature-columns.md)と設定のdisplay_groupsを正本とする。比較候補は密度・構成比・集中度。面積・件数・欠損率・release等は監査にも使う。件数と密度の二重評価、構成比の総和制約があるので、類似度へ投入する列や正規化は次回決める。

## 図と根拠ファイル

以下はすべて `projects/poi/` からの相対パス。生成物はGit管理外で、ブログ担当が同じローカルファイルを利用する。公開リポジトリには図の生成コードを置く。

| 図・資料 | ファイル | キャプション案 |
| --- | --- | --- |
| 主成果：数値プロフィール | `data/cache/region_features/kichijoji-v1/region_profile.svg` | 吉祥寺駅周辺の実験用矩形を数値プロフィールとして表示。生の単位と構成比で示し、類似度用の正規化はしていない。 |
| 主成果：地域特徴量表 | `data/cache/region_features/kichijoji-v1/region_features.csv` | 1地域1行、固定15列。shareは0〜1の丸め前の値。 |
| 算出根拠：密度地図・感度比較 | `data/cache/region_features/kichijoji-v1/density_250_500.svg` | 同じOverture登録3,666件を250m・500m格子で集計。色はAOI内の実面積当たり密度、数字は件数。両図は共通色尺度。 |
| カテゴリ構成図 | `data/cache/region_features/kichijoji-v1/category_composition_250.svg` | 全25区画のカテゴリ構成比。分母は欠損も含む各区画の登録件数。左に件数、右に対象面積を併記。 |
| 実行済みNotebook | `data/cache/region_features/kichijoji-v1/05_region_features.executed.ipynb` | 内容確認用。Gitへ追加しない。 |
| 実行結果HTML | `data/cache/region_features/kichijoji-v1/05_region_features.html` | 図と実測出力をまとめて閲覧するローカル資料。 |
| 数値根拠 | 同フォルダの `cells_250.csv` / `cells_500.csv` / `display_group_250.csv` / `status_250.csv` / `manifest.json` | 個別POIを転載せず、記事内の数値を照合する。 |

構成図の行・列番号は密度図の軸番号と対応する。署名は右上のタイトル行、出典は図の下。記事内に[Overture Attribution](https://docs.overturemaps.org/attribution/)へのリンク、release `2026-09-23.0`、取得日2026-09-25を記載する。SVGをブログ側で別形式に変換するときも凡例・出典を切り落とさない。

## 記事構成案

1. 地域特徴量とは何か
2. 吉祥寺駅周辺を1行の数値にする
3. 各数値は何を意味するか
4. 250m格子から密度と集中度をどう求めたか
5. カテゴリ欠損・営業状態・AOIの限界
6. 次回、同じ特徴量で複数の街を比較する

掲載コードは次の範囲で十分。入力検証・投影・集計・境界検査は関数内にあり、詳細はGitHubへ案内する。

```python
from geoai_open_lab.region_features import run_experiment
from geoai_open_lab.region_figures import save_figures

results, manifest, output_dir = run_experiment()
figures = save_figures(results, output_dir)
import pandas as pd
pd.read_csv(output_dir / "region_features.csv")
```

再現コマンド・入力準備は[利用ガイド](region-features.md#再現)、数値・テストは[検証記録](region-features-validation.md)。新規cloneに固定入力は付属しない。一般読者にも実行できる状態の説明と、取得済みデータが必要という条件を省略しない。

## 言えること・言えないこと

- 言える：この保存済みreleaseと矩形AOIでは、登録密度・カテゴリ構成に区画間の違いが見える。同じ件数と同じ構成比は別の意味を持つ。
- 言えない：全店舗の網羅、営業中店舗数、人流、売上、地域の魅力・優劣、実商圏、他地域との類似度。
- 今回は吉祥寺の矩形内部だけ。街同士の比較・普遍的地域分類・クラスタリング・Embeddingはまだ行っていない。背景地図は使っておらず、特定の通りや駅出口の性質まで図だけから推測しない。

## 記事からのリンク先

1. [公開用Notebook](https://github.com/isshiki/geoai-open-lab/blob/main/projects/poi/notebooks/05_region_features.ipynb)
2. [利用ガイド](https://github.com/isshiki/geoai-open-lab/blob/main/projects/poi/docs/region-features.md)
3. [検証記録](https://github.com/isshiki/geoai-open-lab/blob/main/projects/poi/docs/region-features-validation.md)

記事の原稿を作った後、ラボ側で数値・定義・出典・図の解釈を照合する。ここから他チャットへの送信やブログ公開は行わない。
