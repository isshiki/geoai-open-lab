# 地域Embeddingの実行方法

[Notebook 08](../notebooks/08_region_embedding.ipynb) / [設計](embedding-design.md) / [次元選択](embedding-selection.md) / [検証](embedding-validation.md) / [記事資料](embedding-article-handoff.md)

`projects/poi/`から既存uv環境で実行する。OSのPythonへインストールしない。新規データ・依存の取得は行わない。

```powershell
uv run --locked --offline --group clustering --group osm --group notebooks python -m geoai_open_lab.region_embedding --dimension 64
uv run --locked --offline --group clustering --group osm --group notebooks python scripts/execute_embedding_notebook.py
node scripts/render_embedding_figures.cjs
uv run --locked --offline --group clustering --group osm --group notebooks python scripts/validate_embedding_artifacts.py
```

Notebook実行も全分析を再実行するため、CLIとNotebookを両方実行する必要はない。
保存済み入力がなければ停止する。入力の準備経緯は[類似検索](similar-regions.md)、前回所属は[クラスタリング](clustering.md)。オンライン再取得や最新releaseへの切替はしない。

`embedding_input.load_categories()`は入力SHA、駅ID、AOI内件数を検査し、共有POIの割当行列とprimaryカテゴリ件数を作る。
`region_embedding.run_embedding()`は前回Aの再現照合、TF-IDF、SVD、次元・seed・POI分割・重複の感度確認、k=3分類、寄与分解、manifest保存を行う。
`embedding_figures.save_embedding_figures()`は実測出力からSVG7枚を作る。PNGは既存Playwright/ブラウザを使う`node scripts/render_embedding_figures.cjs`で生成する。追加インストールは必要ない既存環境で行う。

`data/cache/embedding/tokyo-v1/`は同一固定実験の再実行で上書きする。CSV/行列/図/HTML/NotebookはGit管理外。
POI名・チェーン名は読まず、primaryだけ使用。alternatesは使わない。語彙の5駅条件は学習標本の空間重複にも影響される。

## 数学的な意味

TF-IDFの列はカテゴリ。TFは件数、IDFは`log((1+n)/(1+df))+1`、行をL2正規化。カテゴリを一様に重要にする方式ではない。
SVDは非中心化TF-IDFを圧縮する線形法。説明分散はscikit-learnの`explained_variance_ratio_`合計（圧縮後L2正規化前）。正解の説明率ではない。
前回PCAは中心化した8特徴を2次元表示し、分類は8次元で行った。今回SVDは961列を64列へ縮め、その64次元を検索・分類に使用する。両者は特異値分解と関連するが、入力・中心化・用途が異なる。

カテゴリ寄与はコサイン内積の加法分解で、順位変化の因果説明ではない。Bはカテゴリ積、Cは低ランク射影を挟んだ内積分解。負の係数もあり得る。潜在軸の符号と群番号は意味のある順序ではない。
[データポリシー](../../../docs/data-policy.md)と[出典条件](region-feature-sources.md)を維持。元データのsources/licenseを残し、加工日・Foursquare NOTICEとApache本文を成果物へ引き継ぐ。派生ベクトルの公開許諾を包括的に判断しない。

## 図版だけを再生成する

モデル学習やNotebook全セル実行をせず、保存済み結果から表示だけを更新する場合は次を実行する。

```powershell
uv run --locked --offline --group clustering --group osm --group notebooks python -c "from geoai_open_lab.embedding_figures import save_embedding_figures; save_embedding_figures('data/cache/embedding/tokyo-v1')"
node scripts/render_embedding_figures.cjs
```

2026-10-17の改訂ではこの経路のみを使用。入力・学習コード・公開Notebook・CSV・行列・manifestは変更しない。旧実行HTMLには当時の図が埋め込まれるため、記事には改訂後の独立SVG/PNGを使う。

後続の[AOIサイズ感度検証](aoi-sensitivity.md)では500m基準を再現してから半幅600〜800mへ拡張。本ページの元実験は変更していません。
