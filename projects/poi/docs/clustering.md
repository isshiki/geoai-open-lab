# POI地域特徴量のクラスタリング

東京都内656駅の保存済み特徴量を分類する。新しいデータのダウンロードや前回の再集計は行わない。

[Notebook 07](../notebooks/07_region_clustering.ipynb) / [事前設計](clustering-design.md) / [主kの選択](clustering-selection.md) / [検証](clustering-validation.md) / [記事引き継ぎ](clustering-article-handoff.md)。

## 再実行

Pythonはuv管理のテーマ専用`.venv`を使う。OS標準Pythonやグローバル環境へパッケージを追加しない。追加依存は`clustering`グループに分離し、`uv.lock`を固定する。実行も`uv run --locked`を使用する。今回、既存依存のバージョンは変更していない。

`projects/poi/`で実行する。前回のローカル固定入力が必要で、Git cloneだけではデータは揃わない。入力がなければ[前回手順](similar-regions.md)を参照し、別releaseへの自動切替は行わない。

```powershell
uv sync --locked --group clustering --group notebooks --group osm
uv run --locked --group clustering python -m geoai_open_lab.region_clustering --k 3
uv run --locked --group clustering --group notebooks python scripts/execute_clustering_notebook.py
uv run --locked --group clustering python scripts/validate_clustering_artifacts.py
```

Notebook内の図生成はSVGのみで追加描画ライブラリ不要。PNGはPlaywrightと利用可能なブラウザで`node scripts/render_clustering_figures.cjs`を実行する。ブラウザ実行ファイルは任意の環境変数`BROWSER_EXECUTABLE`で指定。未導入の場合は自動ダウンロードしない。

## 計算

`load_inputs()`は設定の固定manifestと2つのCSVのSHA-256、行数、駅IDを確認する。`transform()`は密度・集中度のlog1p、全駅の中央値・IQR標準化、6カテゴリ各列の1/√6倍を行う。前回と同じ距離表現であり、登録数・その他・欠損率等は投入しない。

`run_clustering(k=3)`はk=3〜8の比較、各10seed（1seedあたり30初期化）、Wardとの比較、採用kでの重複監査・代表駅・PCAを計算してGit管理外へ出力する。K-meansは8次元ユークリッド二乗距離を最小化。全点等重みで人口やPOI件数による重み付けはしない。

EPSG:6677はJGD2011 / 平面直角座標系第IX系。既存1km四方と250m格子をメートル単位で定義する座標系で、今回変更しない。PCAはこの地理座標の変換ではなく、8つの特徴の表示用射影である。

## 出力と読み方

- `k_metrics.csv`：3指標・件数・seed/手法安定性。`seed_pair_stability.csv`は全45seedペア×6k。
- `assignments.csv`：全656駅の所属、表示用PCA、感度確認の所属。クラスタ番号は密度中央値順。
- `cluster_summary.csv`：件数・重心から近い3駅・遠い所属例。
- `cluster_features.csv`：各列の中央値・平均差。構成比の平均差は比率単位、記事では100倍してpercentage pointとする。
- `overlap_pairs.csv`・`overlap_clusters.csv`・`suppressed_cross.csv`：重複と感度確認。
- `manifest.json`：入力ハッシュ、版、実行日時UTC、環境、計算条件、出力ハッシュ。

指標やARIの説明は[scikit-learn公式](https://scikit-learn.org/stable/modules/clustering.html)。ARI=1は同じ分割、0は偶然一致の基準。正解ラベルに対する精度ではない。群平均差は分類の説明であり因果的な重要度ではない。主結果は[選択記録](clustering-selection.md)に基づく。

## 公開条件

コード・出力なしNotebook・方法/検証文書のみGit公開。CSV・図・HTML・manifest・生データはテーマ内dataに保存しGit管理外。元の出典・利用条件は[前回設計](similar-regions-design.md)と[出典](region-feature-sources.md)。Overture releaseと取得日、N02/N03 CC BY 4.0、Foursquare由来Apache-2.0とNOTICEを維持し、加工日2026-10-16を追記。図配布時は同梱NOTICEとライセンスを添える。
