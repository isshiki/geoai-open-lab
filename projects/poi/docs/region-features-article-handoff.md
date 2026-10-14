# 記事引き継ぎ：地域特徴量

仮タイトル：**POIデータから地域特徴量を作る：街を数値で表してみる**

実装と固定入力による実行は完了。記事の執筆・ブログ投稿は未実施。Notebook番号05はPOIテーマ内の実行順で、記事番号ではない。

## 読者に伝える発見

1. 登録件数は規模、面積当たり密度は集中、カテゴリ構成比は内訳を表す。吉祥寺の矩形にある3,666件を250mで25区画へ分けると、区画ごとに構成が異なる。
2. 隣り合う `(-93,-132)` と `(-92,-132)` は、食事群がどちらも205件。それでも全件数707・615を分母にすると、約29.0%・33.3%になる。同じ件数でも地域内で占める割合は違う。表示群の定義はrestaurantとcasual_eateryだけであることを添える。
3. 250mの最大密度11,312件/km²に対し、500mでは最大6,393件/km²。同じ3,666件でも、まとめ方で集中の見え方が変わる。最大値の比較であり、全区画の密度が一様に下がるという主張ではない。
4. カテゴリ欠損55件、営業状態欠損3,665件。これは営業中店舗の分布を証明する分析ではない。

2は実行後に見つけた説明用の例。今回の観察から吉祥寺全域や他都市の一般法則、出店適性を主張しない。

## 図と根拠ファイル

以下はすべて `projects/poi/` からの相対パス。生成物はGit管理外で、ブログ担当が同じローカルファイルを利用する。公開リポジトリには図の生成コードを置く。

| 図・資料 | ファイル | キャプション案 |
| --- | --- | --- |
| 密度地図・感度比較 | `data/cache/region_features/kichijoji-v1/density_250_500.svg` | 同じOverture登録3,666件を250m・500m格子で集計。色はAOI内の実面積当たり密度、数字は件数。両図は共通色尺度。 |
| カテゴリ構成図 | `data/cache/region_features/kichijoji-v1/category_composition_250.svg` | 全25区画のカテゴリ構成比。分母は欠損も含む各区画の登録件数。左に件数、右に対象面積を併記。 |
| 実行済みNotebook | `data/cache/region_features/kichijoji-v1/05_region_features.executed.ipynb` | 内容確認用。Gitへ追加しない。 |
| 実行結果HTML | `data/cache/region_features/kichijoji-v1/05_region_features.html` | 図と実測出力をまとめて閲覧するローカル資料。 |
| 数値根拠 | 同フォルダの `cells_250.csv` / `cells_500.csv` / `display_group_250.csv` / `status_250.csv` / `manifest.json` | 個別POIを転載せず、記事内の数値を照合する。 |

構成図の行・列番号は密度図の軸番号と対応する。署名は右上のタイトル行、出典は図の下。記事内に[Overture Attribution](https://docs.overturemaps.org/attribution/)へのリンク、release `2026-09-23.0`、取得日2026-09-25を記載する。SVGをブログ側で別形式に変換するときも凡例・出典を切り落とさない。

## 記事構成案

地域特徴量とは → 固定入力とAOI → 件数・密度・構成比の定義 → 250mの地図 → 同じ205件の構成比の違い → 500mへの集約 → 欠損と限界 → 次は比較対象を決めて類似地域検索。

掲載コードは次の範囲で十分。入力検証・投影・集計・境界検査は関数内にあり、詳細はGitHubへ案内する。

```python
from geoai_open_lab.region_features import run_experiment
from geoai_open_lab.region_figures import save_figures

results, manifest, output_dir = run_experiment()
figures = save_figures(results, output_dir)
manifest["summary"]
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
