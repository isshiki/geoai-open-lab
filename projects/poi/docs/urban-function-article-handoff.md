# 記事引き継ぎ：POIの影響範囲をPythonで推定する

仮タイトル：**POIの影響範囲をPythonで推定する　固定半径・適応半径を比較**。
一般向け候補「街の機能はどこで入れ替わる？」は、住宅入力不足により今回の主張としては採用しない。

[Notebook 15](../notebooks/15_urban_function.ipynb) / [実装](../src/geoai_open_lab/urban_function.py) / [方法](urban-function.md) / [実測値](urban-function-validation.md) / [出典](urban-function-sources.md)

## 記事にする価値と結論

**条件付きで記事化する価値がある。** きれいな都市機能境界が得られた成功談ではなく、「論文の式を動かしても、POIの偏りと半径・正規化で結果が変わる」という追試の記事にする。住宅を含む商業・住宅・緑地の遷移図として公開しない。

8,750件の入力で一般住宅候補は1件。商業6群4,076件と緑地等222件から2機能を推定したが、適応方式は16km²中15.78km²で緑地等が優勢になった。独立の公園・緑地を全部拾ってもconsistencyは0.2651%。半径摂動に対する安定性と、現実との一致は別である。

## 読者に伝える順序

1. POIの影響は距離で弱まる、と仮定して地図を作る。
2. 商業・住宅・緑地を描く前にカテゴリを監査する。住宅不足は計算で埋めない。
3. 固定区画、共通ガウス半径、適応半径の3方式を同じ入力で比較。
4. まばらな緑地等のKNN距離が長く、適応h中央値324.72m。商業は22.40m。
5. 広いhほど総影響量が増える式と、機能別min–max正規化の働きを説明。
6. 安定して再計算できても正しいとは限らない。completenessとconsistencyを並べる。
7. 今後は住宅入力・施設規模・独立検証の意味の対応を改善してから別条件を試す。

## 掲載コード

既存のuv環境と固定入力が必要。自動的に最新データへ追従しない。

```python
from geoai_open_lab.urban_function import run, OUT
from geoai_open_lab.urban_function_figures import render
report, comparisons, external = run()
print(report['function_counts'])
render()
```

核となる式は `D=k/(pi*d**2)`、`C=0.5+0.5*D_normalized`、`h=hmin+(hmax-hmin)*expit(4*(C-0.5))`、`exp(-distance**2/(2*h**2))`。今回S=1。0.5/0.5は論文の補足未確認のため独自ベースラインと明記。出力の帰属度は機能別正規化を挟むので、POI件数構成比ではない。

## 図版対応表

すべて `projects/poi/data/cache/urban_function/kichijoji-v1/` 以下、SVGと同名PNG。Git管理外。白地・淡いカード・右上masahiko.infoの既存体系を継承。商業は橙、緑地等は青、住宅未推定は灰。色だけに依存せず機能名と数値を併記。

| ファイル | キャプション・alt案 |
|---|---|
| input_audit.svg / .png | 商業4,076点、緑地等222点に対し住宅は1点。北が上の同じ4km四方で位置を確認 |
| membership.svg / .png | 固定区画・共通半径・適応半径の2機能混色。住宅は推定していない。灰は未定義 |
| intensity.svg / .png | 適応半径の商業・緑地等の生強度。各機能ごとのlog1p色尺度。住宅は空欄 |
| dominant_mixing.svg / .png | 最大帰属度の機能と2機能の混合度。論文S2の閾値による遷移帯判定ではない |
| transect.svg / .png | 駅の北50mの東西横断線。0～1の帰属度は需要や利用者数ではない |
| difference.svg / .png | 適応−共通半径の緑地等帰属度。方式間の差であって、正解からの誤差ではない |
| cover_1600x900.svg / .png | 住宅入力不足と外部一致の限界を明示する部分追試のカバー |

実行結果は `15_urban_function.html`、実行済みNotebookは `15_urban_function.executed.ipynb`。CSVの `comparison`、`radii`、`category_audit`、`external_validation`、`land_reference_audit`、manifestが数値の根拠。

## 言えること・言えないこと

- 半径と機能別正規化で影響地図は大きく変わった。共通h19mは100m格子に対して小さいため、事後探索の100/250/500mも隠さず示す。
- 同じPOIから計算した方式間の一致は外部検証ではない。国土数値情報2021だけを独立の参照と呼ぶが、時点と機能定義は一致しない。
- 適応方式の精度向上や論文より高性能とは言えない。住宅0件の街ではなく、住宅を観測できていないデータである。
- 出力は機能的影響のグラデーション。土地利用・用途地域・商圏・徒歩到達圏・需要・売上・住みやすさの正解ではない。
- S2未取得のため、混合度の連続地図を「論文と同じ複合機能・遷移帯」と説明しない。
- 論文のTable 5のMAEは1超の表示だが、単位の換算根拠を確認できないため本実験のMAEと直接比較しない。
- 出典は論文DOI、OvertureとFoursquare NOTICE、国土数値情報N02-25・土地利用2021を明記。既存Notebookと数値は変更していない。
