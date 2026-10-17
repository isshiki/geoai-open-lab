# AOI感度検証：記事引き継ぎ

仮タイトル：**街をどこまで数える？ Pythonで駅周辺の範囲と類似順位を検証してみた**

記事の主題は「500mと800mのどちらが正しいか」ではなく、対象範囲に対する結果の感度。半幅500m＝1km四方、800m＝1.6km四方と最初に説明する。

## 主な発見

- 500mの既存結果を再現した上で比較。主比較の候補集合は800m基準に統一。
- 吉祥寺のCは500mで町田1位、800mで都電雑司ヶ谷1位・町田2位。共通は5/10駅。
- 全駅平均の500→800m上位10共通数はA 1.97、B 3.31、C 3.19駅。Embeddingだけが変わったわけではない。
- Cの分類ARIは0.609954、最大一致対応後の所属変更は97/656駅。吉祥寺は群3を維持。上位10と大きな3群の一致は別の尺度。
- Cで石神前・柴崎体育館・京成関屋は共通0駅。六本木・自由が丘・浅草は8駅。平均だけでは個別の違いを説明できない。
- 800mではAの最大密度が部分格子にある駅が334。Aの変化には端の区画と標準化の影響も含まれる。

## 記事の順序

1. なぜ集計範囲を検証するか
2. 同じ駅・release・961カテゴリと、共通の候補除外
3. 吉祥寺の順位の変化
4. 全656駅では分布を見る
5. 3群分類とAOIの重なり
6. 範囲は分析条件であり、正解や商圏ではない

## 実測値と再現

全AOI×A/B/Cのトップ10、全駅平均・中央値・Spearman、クラスタと代表駅は[検証記録](aoi-sensitivity-validation.md)。数値の正本はローカル `data/cache/aoi_sensitivity/tokyo-v1/` のrankings.csv、summary.csv、station_stability.csv、cluster_metrics.csv、cluster_summary.csv、audit.csv、overlap_pairs.csv、manifest.json。

[Notebook 09](../notebooks/09_aoi_sensitivity.ipynb) / [計算方法と実行手順](aoi-sensitivity.md)。

```python
from geoai_open_lab.aoi_sensitivity import run
summary, manifest, out = run()
summary.round(3)
```

## 図版

すべてテーマ内のGit管理外。SVGと同名PNGがあり、ブログ側で利用する前に同梱NOTICE・出典・変更日を保持する。

- `aoi_sizes.svg` / [PNG](../data/cache/aoi_sensitivity/tokyo-v1/aoi_sizes.png)：駅中心の正方形は1.00〜2.56km²。500〜800mは半幅。
- `target_rankings.svg` / [PNG](../data/cache/aoi_sensitivity/tokyo-v1/target_rankings.png)：吉祥寺の上位10駅。共通・新規・圏外を区別。
- `common_distribution.svg` / [PNG](../data/cache/aoi_sensitivity/tokyo-v1/common_distribution.png)：656駅に対する上位10共通数の分布。
- `station_sensitivity.svg` / [PNG](../data/cache/aoi_sensitivity/tokyo-v1/station_sensitivity.png)：POI数と共通数、変化の大きい例・小さい例。
- `cluster_changes.svg` / [PNG](../data/cache/aoi_sensitivity/tokyo-v1/cluster_changes.png)：Cの500→800mの最大一致対応後のクロス表。
- `cover_1600x900.svg` / [PNG](../data/cache/aoi_sensitivity/tokyo-v1/cover_1600x900.png)：カバー：範囲変更で3方式とも結果が変わった。

[実行結果HTML](../data/cache/aoi_sensitivity/tokyo-v1/09_aoi_sensitivity.html)。公開コードは [GitHub Notebook](https://github.com/isshiki/geoai-open-lab/blob/main/projects/poi/notebooks/09_aoi_sensitivity.ipynb) と [実装](https://github.com/isshiki/geoai-open-lab/blob/main/projects/poi/src/geoai_open_lab/aoi_sensitivity.py)。

## 書けないこと

800mの方が高精度、最適商圏、順位が変わるから無意味、Embeddingだけ不安定とは書かない。既存3クラスタは優劣・Tierでない。追加されたカテゴリを順位変化の原因と断定しない。AOI重複する駅群を独立した街の発見として数えない。rental_kioskの具体的内容は未確認なので本文例から外す。

Aは密度・構成比・集中度、B/Cは細分類構成。さらに部分格子・再学習・語彙固定が影響するため、方式間の差を単一原因で説明しない。次の候補は格子端の扱いを固定した追加感度や円形との比較だが、今回は未実施。

全駅を個別に調べる場合は、同じ成果物フォルダのall_station_top10.csv（78,720行）を使用する。query_region_idで照会駅を選び、modeとhalf_width_mを指定すると上位10駅と500m順位が分かる。
